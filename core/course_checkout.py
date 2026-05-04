"""Course catalog cart + Razorpay Standard Checkout."""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

import razorpay.errors as rz_errors

from payments.services import get_razorpay_client, razorpay_dummy_mode

from .models import Course, CourseOrder
from .services_course_checkout import (
    cart_course_ids,
    complete_course_order_after_payment,
    complete_free_checkout,
    create_course_checkout_order,
    resolve_cart_courses,
    set_cart_course_ids,
    user_owned_course_ids,
)


@login_required
def course_cart(request):
    courses, total = resolve_cart_courses(request.user, request)
    return render(
        request,
        "core/course_cart.jinja",
        {
            "cart_courses": courses,
            "cart_total_inr": total,
            "payment_dummy": razorpay_dummy_mode(),
            "checkout_success_url": reverse("core:courses") + "?purchased=1",
            "seo_title": "Course cart | RankJee",
            "seo_description": "Review courses and pay securely with Razorpay.",
            "canonical_url": request.build_absolute_uri(request.path),
            "seo_noindex": True,
        },
    )


@login_required
@require_POST
def course_cart_add(request, course_id):
    course = get_object_or_404(Course, id=course_id, is_active=True)
    owned = user_owned_course_ids(request.user)
    if course.id in owned:
        return redirect(request.POST.get("next") or reverse("core:course_cart"))
    ids = cart_course_ids(request)
    if course.id not in ids:
        ids.append(course.id)
        set_cart_course_ids(request, ids)
    next_url = (request.POST.get("next") or "").strip()
    if next_url.startswith("/"):
        return redirect(next_url)
    return redirect("core:course_cart")


@login_required
@require_POST
def course_cart_remove(request, course_id):
    ids = [i for i in cart_course_ids(request) if i != int(course_id)]
    set_cart_course_ids(request, ids)
    return redirect("core:course_cart")


@login_required
@require_POST
def course_checkout_create(request):
    courses, total = resolve_cart_courses(request.user, request)
    if not courses:
        return JsonResponse({"error": "Your cart is empty or courses were already purchased."}, status=400)

    if total <= 0:
        complete_free_checkout(request.user, courses, request)
        return JsonResponse(
            {
                "checkout_mode": "free",
                "redirect": reverse("core:courses") + "?purchased=1",
            }
        )

    payload = create_course_checkout_order(request.user, courses, total)
    if "error" in payload:
        status = int(payload.get("http_status") or 400)
        return JsonResponse({"error": payload["error"]}, status=status)

    payload["user_name"] = request.user.username
    payload["user_email"] = request.user.email or ""
    payload["name"] = "RankJee Courses"
    return JsonResponse(payload)


@login_required
@require_POST
def course_checkout_verify(request):
    params_dict = {
        "razorpay_order_id": request.POST.get("razorpay_order_id"),
        "razorpay_payment_id": request.POST.get("razorpay_payment_id"),
        "razorpay_signature": request.POST.get("razorpay_signature"),
    }
    if not params_dict["razorpay_order_id"]:
        return JsonResponse({"status": "failed", "error": "Missing order id"}, status=400)

    try:
        order = CourseOrder.objects.get(razorpay_order_id=params_dict["razorpay_order_id"])
    except CourseOrder.DoesNotExist:
        return JsonResponse({"status": "failed", "error": "Order not found"}, status=400)

    if order.user_id != request.user.id:
        return JsonResponse({"status": "failed", "error": "Forbidden"}, status=403)

    if order.status != CourseOrder.Status.PENDING:
        return JsonResponse({"status": "success", "message": "Already processed"})

    if razorpay_dummy_mode():
        complete_course_order_after_payment(
            order,
            request.user,
            params_dict["razorpay_payment_id"] or "pay_dummy",
            params_dict["razorpay_signature"] or "dummy",
            request,
        )
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
        order.status = CourseOrder.Status.FAILED
        order.save(update_fields=["status"])
        return JsonResponse({"status": "failed", "error": str(e)}, status=400)

    try:
        complete_course_order_after_payment(
            order,
            request.user,
            params_dict["razorpay_payment_id"],
            params_dict["razorpay_signature"],
            request,
        )
    except Exception:
        order.status = CourseOrder.Status.FAILED
        order.save(update_fields=["status"])
        return JsonResponse(
            {"status": "failed", "error": "Payment captured but post-payment processing failed. Please contact support."},
            status=500,
        )
    return JsonResponse({"status": "success"})
