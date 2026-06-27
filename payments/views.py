import uuid
from datetime import timedelta

import razorpay.errors as rz_errors
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import PaymentOrder, SubscriptionPlan, UserSubscription
from .services import get_razorpay_client, make_dummy_order_id, razorpay_dummy_mode


def _exam_subscription_success_url(user) -> str:
    """Post-checkout landing: exam catalog for subscribers; command centre for staff."""
    suffix = "?paid=1"
    if user.is_staff or user.is_superuser:
        return reverse("dashboard:index") + suffix
    return reverse("assessment:index") + suffix


def plans_view(request):
    plans = list(SubscriptionPlan.objects.filter(is_active=True).order_by("price"))
    has_monthly = any(p.duration_days <= 30 for p in plans)
    has_annual = any(p.duration_days > 30 for p in plans)
    # Alpine default tab: if only annual plans exist, start on "annual" or the grid looks empty.
    if has_monthly:
        plans_billing_default = "monthly"
    elif has_annual:
        plans_billing_default = "annual"
    else:
        plans_billing_default = "monthly"
    ctx = {
        "plans": plans,
        "plans_billing_default": plans_billing_default,
        "has_monthly_plans": has_monthly,
        "has_annual_plans": has_annual,
        "payment_dummy": razorpay_dummy_mode(),
        "referral_premium_enabled": getattr(settings, "REFERRAL_PREMIUM_ENABLED", False),
        "referral_premium_days": getattr(settings, "REFERRAL_PREMIUM_DAYS", 0),
        "signup_trial_enabled": getattr(settings, "SIGNUP_TRIAL_ENABLED", False),
        "signup_trial_days": getattr(settings, "SIGNUP_TRIAL_DAYS", 0),
        "payment_success_url": (
            _exam_subscription_success_url(request.user)
            if request.user.is_authenticated
            else reverse("assessment:index") + "?paid=1"
        ),
    }
    return render(request, "payments/plans.jinja", ctx)


@login_required
@require_POST
def create_order(request, plan_id):
    plan = get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)
    amount_paise = int(plan.price * 100)

    if razorpay_dummy_mode():
        rid = make_dummy_order_id()
        PaymentOrder.objects.create(
            user=request.user,
            plan=plan,
            amount=plan.price,
            razorpay_order_id=rid,
        )
        return JsonResponse(
            {
                "checkout_mode": "dummy",
                "order_id": rid,
                "amount": amount_paise,
                "currency": "INR",
                "key": "rzp_test_DUMMYLOCAL",
                "name": plan.name,
                "description": plan.description or plan.name,
                "user_name": request.user.username,
                "user_email": request.user.email or "",
            }
        )

    client = get_razorpay_client()
    if not client:
        return JsonResponse({"error": "Razorpay is not configured."}, status=400)

    if amount_paise < 100:
        return JsonResponse(
            {"error": "Amount must be at least ₹1 (100 paise) for Razorpay checkout."},
            status=400,
        )

    # Razorpay receipt max length 40
    receipt = f"rj_{uuid.uuid4().hex}"[:40]
    order_data = {
        "amount": amount_paise,
        "currency": "INR",
        "receipt": receipt,
        "payment_capture": "1",
    }
    try:
        razorpay_order = client.order.create(data=order_data)
    except rz_errors.BadRequestError as e:
        msg = str(e)
        lower = msg.lower()
        if any(
            w in lower
            for w in ("authentication", "credential", "unauthorized", "not authorised")
        ):
            return JsonResponse({"error": msg}, status=401)
        return JsonResponse({"error": msg}, status=400)
    except (rz_errors.GatewayError, rz_errors.ServerError) as e:
        return JsonResponse({"error": str(e)}, status=500)

    PaymentOrder.objects.create(
        user=request.user,
        plan=plan,
        amount=plan.price,
        razorpay_order_id=razorpay_order["id"],
    )
    return JsonResponse(
        {
            "checkout_mode": "live",
            "order_id": razorpay_order["id"],
            "amount": amount_paise,
            "currency": razorpay_order.get("currency", "INR"),
            "key": settings.RAZORPAY_KEY_ID,
            "name": plan.name,
            "description": plan.description or plan.name,
            "user_name": request.user.username,
            "user_email": request.user.email or "",
        }
    )


def _apply_successful_order(order: PaymentOrder, user):
    plan_obj = order.plan
    now = timezone.now()
    sub, created = UserSubscription.objects.get_or_create(
        user=user,
        defaults={
            "plan": plan_obj,
            "end_date": now + timedelta(days=plan_obj.duration_days),
            "is_active": True,
        },
    )
    if not created:
        sub.plan = plan_obj
        base = sub.end_date if sub.end_date > now else now
        sub.end_date = base + timedelta(days=plan_obj.duration_days)
        sub.is_active = True
        sub.save()
    from core.middleware import invalidate_user_premium_cache
    invalidate_user_premium_cache(user.pk)


@login_required
@require_POST
def verify_payment(request):
    params_dict = {
        "razorpay_order_id": request.POST.get("razorpay_order_id"),
        "razorpay_payment_id": request.POST.get("razorpay_payment_id"),
        "razorpay_signature": request.POST.get("razorpay_signature"),
    }
    if not params_dict["razorpay_order_id"]:
        return JsonResponse({"status": "failed", "error": "Missing order id"}, status=400)

    try:
        order = PaymentOrder.objects.get(razorpay_order_id=params_dict["razorpay_order_id"])
    except PaymentOrder.DoesNotExist:
        return JsonResponse({"status": "failed", "error": "Order not found"}, status=400)

    if order.user_id != request.user.id:
        return JsonResponse({"status": "failed", "error": "Forbidden"}, status=403)

    if order.status != "PENDING":
        return JsonResponse({"status": "success", "message": "Already processed"})

    if razorpay_dummy_mode():
        order.razorpay_payment_id = params_dict["razorpay_payment_id"] or "pay_dummy"
        order.razorpay_signature = params_dict["razorpay_signature"] or "dummy"
        order.status = "SUCCESS"
        order.save()
        _apply_successful_order(order, request.user)
        return JsonResponse({"status": "success"})

    client = get_razorpay_client()
    if not client:
        return JsonResponse({"status": "failed", "error": "Razorpay not configured"}, status=400)

    if not params_dict["razorpay_payment_id"] or not params_dict["razorpay_signature"]:
        return JsonResponse(
            {"status": "failed", "error": "Missing payment id or signature"},
            status=400,
        )

    try:
        client.utility.verify_payment_signature(params_dict)
    except rz_errors.SignatureVerificationError as e:
        order.status = "FAILED"
        order.save()
        return JsonResponse({"status": "failed", "error": str(e)}, status=400)

    order.razorpay_payment_id = params_dict["razorpay_payment_id"]
    order.razorpay_signature = params_dict["razorpay_signature"]
    order.status = "SUCCESS"
    order.save()
    _apply_successful_order(order, request.user)
    return JsonResponse({"status": "success"})
