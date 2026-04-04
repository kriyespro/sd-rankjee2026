from datetime import timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import PaymentOrder, SubscriptionPlan, UserSubscription
from .services import get_razorpay_client, make_dummy_order_id, razorpay_dummy_mode


def plans_view(request):
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by("price")
    return render(
        request,
        "payments/plans.jinja",
        {
            "plans": plans,
            "payment_dummy": razorpay_dummy_mode(),
        },
    )


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

    order_data = {
        "amount": amount_paise,
        "currency": "INR",
        "payment_capture": "1",
    }
    try:
        razorpay_order = client.order.create(data=order_data)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

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

    try:
        client.utility.verify_payment_signature(params_dict)
    except Exception as e:
        order.status = "FAILED"
        order.save()
        return JsonResponse({"status": "failed", "error": str(e)}, status=400)

    order.razorpay_payment_id = params_dict["razorpay_payment_id"]
    order.razorpay_signature = params_dict["razorpay_signature"]
    order.status = "SUCCESS"
    order.save()
    _apply_successful_order(order, request.user)
    return JsonResponse({"status": "success"})
