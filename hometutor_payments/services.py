"""Marketplace fee split, ledger, idempotent payment settlement."""

from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import MarketplaceOrder, TutorLedgerEntry, TutorPayoutRequest


def default_monthly_gross() -> Decimal:
    raw = getattr(settings, 'HOMETUTOR_DEFAULT_MONTHLY_FEE_INR', '5000')
    return Decimal(str(raw))


def platform_fee_split(gross: Decimal) -> tuple[Decimal, Decimal]:
    pct = Decimal(str(getattr(settings, 'HOMETUTOR_PLATFORM_FEE_PERCENT', '15')))
    platform_fee = (gross * pct / Decimal('100')).quantize(Decimal('0.01'))
    tutor_credit = (gross - platform_fee).quantize(Decimal('0.01'))
    return platform_fee, tutor_credit


def _balance_after_last(tutor_profile_id: int) -> Decimal:
    last = (
        TutorLedgerEntry.objects.filter(tutor_profile_id=tutor_profile_id)
        .order_by('-id')
        .first()
    )
    return last.balance_after if last else Decimal('0')


@transaction.atomic
def apply_marketplace_payment_success(
    order: MarketplaceOrder,
    *,
    payment_id: str,
    signature: str = '',
    webhook_event_id: str | None = None,
) -> tuple[MarketplaceOrder, bool]:
    """
    Mark order paid and credit tutor ledger once (idempotent).
    Returns (order, created_ledger).
    """
    order = MarketplaceOrder.objects.select_for_update().get(pk=order.pk)
    if order.status == MarketplaceOrder.Status.SUCCESS:
        return order, False

    tp_id = order.engagement.tutor_profile_id
    bal = _balance_after_last(tp_id)
    new_bal = bal + order.tutor_credit_amount

    order.status = MarketplaceOrder.Status.SUCCESS
    order.razorpay_payment_id = payment_id
    if signature:
        order.razorpay_signature = signature
    if webhook_event_id:
        order.webhook_event_id = webhook_event_id
    order.paid_at = timezone.now()
    order.save(
        update_fields=[
            'status',
            'razorpay_payment_id',
            'razorpay_signature',
            'webhook_event_id',
            'paid_at',
        ]
    )

    le, created = TutorLedgerEntry.objects.get_or_create(
        marketplace_order=order,
        defaults={
            'tutor_profile_id': tp_id,
            'description': f'Marketplace credit (order {order.razorpay_order_id})',
            'amount': order.tutor_credit_amount,
            'balance_after': new_bal,
        },
    )
    return order, created


@transaction.atomic
def apply_payout_paid(payout: TutorPayoutRequest) -> TutorLedgerEntry | None:
    """Debit tutor balance when staff marks payout PAID (idempotent)."""
    if payout.status != TutorPayoutRequest.Status.PAID:
        return None
    if getattr(payout, 'ledger_entry', None):
        return payout.ledger_entry

    tp_id = payout.tutor_profile_id
    bal = _balance_after_last(tp_id)
    amt = -abs(payout.amount)
    new_bal = bal + amt
    return TutorLedgerEntry.objects.create(
        tutor_profile_id=tp_id,
        payout=payout,
        description=f'Payout #{payout.pk} (bank / NEFT)',
        amount=amt,
        balance_after=new_bal,
    )
