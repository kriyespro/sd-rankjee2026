import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from hometutor.models import TutorEngagement

from .models import MarketplaceOrder
from .services import apply_marketplace_payment_success, default_monthly_gross, platform_fee_split

logger = logging.getLogger('rankjee.hometutor_payments')


def _get_razorpay_helpers():
    from payments.services import get_razorpay_client, make_dummy_order_id, razorpay_dummy_mode

    return get_razorpay_client, make_dummy_order_id, razorpay_dummy_mode


@login_required
def pay_checkout(request, engagement_id):
    eng = get_object_or_404(
        TutorEngagement.objects.select_related(
            'demo_request',
            'demo_request__tutor',
            'tutor_profile',
            'marketplace_order',
        ),
        pk=engagement_id,
    )
    if eng.demo_request.requester_id != request.user.id:
        return HttpResponseForbidden('Only the parent/student who booked the demo can pay.')
    if eng.status != TutorEngagement.Status.ACTIVE:
        return HttpResponseForbidden('Engagement must be mutually confirmed before payment.')

    gross = default_monthly_gross()
    pf, tc = platform_fee_split(gross)
    mo = MarketplaceOrder.objects.filter(engagement_id=eng.pk).first()

    _, _, razorpay_dummy_mode = _get_razorpay_helpers()
    fee_pct_label = str(getattr(settings, 'HOMETUTOR_PLATFORM_FEE_PERCENT', '15'))

    return render(
        request,
        'hometutor_payments/pay_engagement.jinja',
        {
            'engagement': eng,
            'gross': gross,
            'platform_fee': pf,
            'tutor_credit': tc,
            'fee_pct_label': fee_pct_label,
            'existing_order': mo,
            'payment_dummy': razorpay_dummy_mode(),
        },
    )


@login_required
@require_POST
def create_order(request, engagement_id):
    get_razorpay_client, make_dummy_order_id, razorpay_dummy_mode = _get_razorpay_helpers()

    eng = get_object_or_404(
        TutorEngagement.objects.select_related('marketplace_order'),
        pk=engagement_id,
    )
    if eng.demo_request.requester_id != request.user.id:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    if eng.status != TutorEngagement.Status.ACTIVE:
        return JsonResponse({'error': 'Engagement not active'}, status=400)

    mo = MarketplaceOrder.objects.filter(engagement_id=eng.pk).first()
    if mo and mo.status == MarketplaceOrder.Status.SUCCESS:
        return JsonResponse({'error': 'Already paid for this engagement.'}, status=400)

    gross = default_monthly_gross()
    pf, tc = platform_fee_split(gross)
    amount_paise = int(gross * 100)

    if razorpay_dummy_mode():
        rid = make_dummy_order_id()
    else:
        client = get_razorpay_client()
        if not client:
            return JsonResponse({'error': 'Razorpay is not configured.'}, status=400)
        try:
            rp = client.order.create(
                {
                    'amount': amount_paise,
                    'currency': 'INR',
                    'payment_capture': 1,
                    'notes': {'engagement_id': str(eng.pk), 'purpose': 'hometutor_marketplace'},
                }
            )
            rid = rp['id']
        except Exception as exc:
            return JsonResponse({'error': str(exc)}, status=400)

    if mo:
        mo.razorpay_order_id = rid
        mo.amount_gross = gross
        mo.platform_fee_amount = pf
        mo.tutor_credit_amount = tc
        mo.status = MarketplaceOrder.Status.PENDING
        mo.save(
            update_fields=[
                'razorpay_order_id',
                'amount_gross',
                'platform_fee_amount',
                'tutor_credit_amount',
                'status',
            ]
        )
    else:
        mo = MarketplaceOrder.objects.create(
            engagement=eng,
            payer=request.user,
            amount_gross=gross,
            platform_fee_amount=pf,
            tutor_credit_amount=tc,
            razorpay_order_id=rid,
        )

    if razorpay_dummy_mode():
        return JsonResponse(
            {
                'checkout_mode': 'dummy',
                'order_id': rid,
                'amount': amount_paise,
                'key': 'rzp_test_DUMMYLOCAL',
                'name': 'Home tutor — first month (marketplace)',
                'description': f'Engagement #{eng.pk} · {eng.tutor_profile.display_name}',
                'user_name': request.user.username,
                'user_email': request.user.email or '',
            }
        )

    return JsonResponse(
        {
            'checkout_mode': 'live',
            'order_id': rid,
            'amount': amount_paise,
            'key': settings.RAZORPAY_KEY_ID,
            'name': 'RankJee home tutor',
            'description': f'Engagement #{eng.pk}',
            'user_name': request.user.username,
            'user_email': request.user.email or '',
        }
    )


@login_required
@require_POST
def verify_payment(request):
    get_razorpay_client, _, razorpay_dummy_mode = _get_razorpay_helpers()

    params_dict = {
        'razorpay_order_id': request.POST.get('razorpay_order_id'),
        'razorpay_payment_id': request.POST.get('razorpay_payment_id'),
        'razorpay_signature': request.POST.get('razorpay_signature'),
    }
    if not params_dict['razorpay_order_id']:
        return JsonResponse({'status': 'failed', 'error': 'Missing order id'}, status=400)

    try:
        order = MarketplaceOrder.objects.select_related('engagement').get(
            razorpay_order_id=params_dict['razorpay_order_id']
        )
    except MarketplaceOrder.DoesNotExist:
        return JsonResponse({'status': 'failed', 'error': 'Order not found'}, status=400)

    if order.payer_id != request.user.id:
        return JsonResponse({'status': 'failed', 'error': 'Forbidden'}, status=403)

    if order.status == MarketplaceOrder.Status.SUCCESS:
        return JsonResponse({'status': 'success', 'message': 'Already processed'})

    if razorpay_dummy_mode():
        apply_marketplace_payment_success(
            order,
            payment_id=params_dict['razorpay_payment_id'] or 'pay_dummy',
            signature=params_dict['razorpay_signature'] or 'dummy',
        )
        return JsonResponse({'status': 'success'})

    client = get_razorpay_client()
    if not client:
        return JsonResponse({'status': 'failed', 'error': 'Razorpay not configured'}, status=400)

    try:
        client.utility.verify_payment_signature(params_dict)
    except Exception as exc:
        order.status = MarketplaceOrder.Status.FAILED
        order.save(update_fields=['status'])
        return JsonResponse({'status': 'failed', 'error': str(exc)}, status=400)

    apply_marketplace_payment_success(
        order,
        payment_id=params_dict['razorpay_payment_id'] or '',
        signature=params_dict['razorpay_signature'] or '',
    )
    return JsonResponse({'status': 'success'})


@csrf_exempt
def razorpay_webhook(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('POST only')

    secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', '') or ''
    body = request.body
    sig = request.headers.get('X-Razorpay-Signature', '')

    if not secret:
        logger.warning('RAZORPAY_WEBHOOK_SECRET unset — refusing webhook')
        return HttpResponse(status=503)

    if secret and body:
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            logger.warning('Razorpay webhook signature mismatch')
            return HttpResponse(status=400)

    try:
        payload = json.loads(body.decode() or '{}')
    except json.JSONDecodeError:
        return HttpResponseBadRequest('invalid json')

    event = payload.get('event') or ''
    event_id = payload.get('id') or ''

    if event != 'payment.captured':
        return HttpResponse(status=200)

    try:
        pay_entity = payload['payload']['payment']['entity']
    except (KeyError, TypeError):
        return HttpResponse(status=200)

    order_id = pay_entity.get('order_id')
    payment_id = pay_entity.get('id')
    if not order_id or not payment_id:
        return HttpResponse(status=200)

    try:
        order = MarketplaceOrder.objects.select_related('engagement').get(razorpay_order_id=order_id)
    except MarketplaceOrder.DoesNotExist:
        return HttpResponse(status=200)

    if order.webhook_event_id == event_id and event_id:
        return HttpResponse(status=200)

    if order.status == MarketplaceOrder.Status.SUCCESS:
        return HttpResponse(status=200)

    try:
        apply_marketplace_payment_success(
            order,
            payment_id=payment_id,
            webhook_event_id=event_id or None,
        )
    except Exception as exc:
        logger.exception('Webhook apply failed: %s', exc)
        return HttpResponse(status=500)

    return HttpResponse(status=200)


@login_required
@require_POST
def request_payout(request):
    """Tutor self-serve payout request for their full current balance.

    Creates a PENDING TutorPayoutRequest — ops still marks PAID manually in /sd/
    (same flow as before; this only removes the "ask support to raise it" step).
    """
    from django.contrib import messages
    from django.shortcuts import redirect

    from hometutor.models import TutorProfile

    from .models import TutorLedgerEntry, TutorPayoutRequest

    profile = TutorProfile.objects.filter(user=request.user).first()
    if not profile:
        messages.error(request, 'No tutor profile found for your account.')
        return redirect('dashboard:index')

    latest_ledger = TutorLedgerEntry.objects.filter(tutor_profile=profile).order_by('-id').first()
    balance = latest_ledger.balance_after if latest_ledger else 0
    if balance <= 0:
        messages.error(request, 'No withdrawable balance yet.')
        return redirect('dashboard:index')
    if TutorPayoutRequest.objects.filter(
        tutor_profile=profile, status=TutorPayoutRequest.Status.PENDING
    ).exists():
        messages.info(request, 'You already have a payout request pending — ops will process it soon.')
        return redirect('dashboard:index')

    TutorPayoutRequest.objects.create(tutor_profile=profile, amount=balance)
    messages.success(request, f'Payout request for ₹{balance} raised — you will be paid by bank transfer.')
    return redirect('dashboard:index')
