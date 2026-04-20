from django.conf import settings
from django.db import models


class MarketplaceOrder(models.Model):
    """Parent pays platform for a confirmed engagement — separate from subscription `payments.PaymentOrder`."""

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SUCCESS = 'SUCCESS', 'Success'
        FAILED = 'FAILED', 'Failed'

    engagement = models.OneToOneField(
        'hometutor.TutorEngagement',
        on_delete=models.PROTECT,
        related_name='marketplace_order',
    )
    payer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='marketplace_orders',
    )
    amount_gross = models.DecimalField(max_digits=12, decimal_places=2)
    platform_fee_amount = models.DecimalField(max_digits=12, decimal_places=2)
    tutor_credit_amount = models.DecimalField(max_digits=12, decimal_places=2)
    razorpay_order_id = models.CharField(max_length=64, unique=True, db_index=True)
    razorpay_payment_id = models.CharField(max_length=64, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=256, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    webhook_event_id = models.CharField(
        max_length=80,
        blank=True,
        null=True,
        help_text='Last Razorpay event id applied (idempotency).',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'MP {self.razorpay_order_id} {self.status} ₹{self.amount_gross}'


class TutorPayoutRequest(models.Model):
    """Manual NEFT / bank payout — staff marks paid in admin."""

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PAID = 'PAID', 'Paid'
        CANCELLED = 'CANCELLED', 'Cancelled'

    tutor_profile = models.ForeignKey(
        'hometutor.TutorProfile',
        on_delete=models.CASCADE,
        related_name='payout_requests',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    bank_reference = models.CharField(
        max_length=120,
        blank=True,
        help_text='UTR / bank reference when paid.',
    )
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Payout {self.pk} ₹{self.amount} ({self.status})'


class TutorLedgerEntry(models.Model):
    """Running balance line for a tutor profile (audit trail)."""

    tutor_profile = models.ForeignKey(
        'hometutor.TutorProfile',
        on_delete=models.CASCADE,
        related_name='ledger_entries',
    )
    marketplace_order = models.OneToOneField(
        MarketplaceOrder,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='ledger_entry',
    )
    payout = models.OneToOneField(
        TutorPayoutRequest,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='ledger_entry',
    )
    description = models.CharField(max_length=255)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='Positive = credit to tutor, negative = debit (payout).',
    )
    balance_after = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.tutor_profile_id} {self.amount} → {self.balance_after}'
