"""Course catalog checkout: Razorpay order + verify (reuses `payments.services` gateway helpers)."""
from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal

import razorpay.errors as rz_errors
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from payments.services import get_razorpay_client, make_dummy_order_id, razorpay_dummy_mode

from .models import Course, CourseOrder, CourseOrderLine, CoursePurchase, CourseReferral


SESSION_CART_KEY = "course_cart_ids"

# Referred leads: buyer pays list minus this percent; affiliate earns commission on actual paid amount.
REFERRAL_LEAD_DISCOUNT_PERCENT = Decimal("15")
REFERRAL_COMMISSION_PERCENT_DEFAULT = Decimal("18")


def _quantize_inr(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def user_has_pending_course_referral(user, course: Course) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return CourseReferral.objects.filter(
        course=course,
        lead_user=user,
        status=CourseReferral.Status.PENDING,
    ).exists()


def unit_checkout_price_inr(course: Course, user) -> Decimal:
    """Unit price charged at checkout (15% off list when this user has a pending referral on the course)."""
    base = course.price_inr if course.price_inr is not None else Decimal("0")
    if user_has_pending_course_referral(user, course):
        discounted = base * (Decimal("100") - REFERRAL_LEAD_DISCOUNT_PERCENT) / Decimal("100")
        return _quantize_inr(discounted)
    return _quantize_inr(base)


def expected_referral_sale_amount_inr(course: Course) -> Decimal:
    """Expected payment amount for a lead who enrolled via a referral link (before checkout)."""
    base = course.price_inr if course.price_inr is not None else Decimal("0")
    discounted = base * (Decimal("100") - REFERRAL_LEAD_DISCOUNT_PERCENT) / Decimal("100")
    return _quantize_inr(discounted)


def cart_course_ids(request) -> list[int]:
    raw = request.session.get(SESSION_CART_KEY) or []
    out: list[int] = []
    for x in raw:
        try:
            pk = int(x)
            if pk > 0:
                out.append(pk)
        except (TypeError, ValueError):
            continue
    # dedupe, preserve order
    seen = set()
    unique = []
    for pk in out:
        if pk not in seen:
            seen.add(pk)
            unique.append(pk)
    return unique


def set_cart_course_ids(request, ids: list[int]) -> None:
    request.session[SESSION_CART_KEY] = list(dict.fromkeys(int(i) for i in ids if int(i) > 0))


def clear_cart(request) -> None:
    request.session.pop(SESSION_CART_KEY, None)


def user_owned_course_ids(user) -> set[int]:
    return set(CoursePurchase.objects.filter(user=user).values_list("course_id", flat=True))


def resolve_cart_courses(user, request) -> tuple[list[Course], Decimal, dict[int, Decimal]]:
    """
    Return active courses in cart excluding already purchased.
    Total is sum of checkout unit prices (15% referral discount when eligible).
    Third value maps course id -> unit price charged for that line.
    """
    ids = cart_course_ids(request)
    owned = user_owned_course_ids(user)
    ids = [i for i in ids if i not in owned]
    if not ids:
        return [], Decimal("0"), {}
    courses = list(Course.objects.filter(id__in=ids, is_active=True).order_by("title"))
    found_ids = {c.id for c in courses}
    # drop missing/inactive from session
    set_cart_course_ids(request, [i for i in ids if i in found_ids])
    unit_prices: dict[int, Decimal] = {}
    total = Decimal("0")
    for c in courses:
        p = unit_checkout_price_inr(c, user)
        unit_prices[c.id] = p
        total += p
    return courses, total, unit_prices


def finalize_referral_commissions(
    user,
    courses: list[Course],
    *,
    paid_unit_prices: dict[int, Decimal] | None = None,
) -> None:
    """Mark matching pending referrals SUCCESS and credit referrer wallet."""
    for course in courses:
        ref = (
            CourseReferral.objects.filter(
                course=course,
                lead_user=user,
                status=CourseReferral.Status.PENDING,
            )
            .select_related("referrer", "course")
            .order_by("-created_at")
            .first()
        )
        if not ref or ref.commission_paid_at:
            continue
        if paid_unit_prices and course.id in paid_unit_prices:
            sale_amount = paid_unit_prices[course.id]
        else:
            sale_amount = unit_checkout_price_inr(course, user)
        percent = ref.commission_percent or REFERRAL_COMMISSION_PERCENT_DEFAULT
        commission = _quantize_inr((sale_amount * percent) / Decimal("100"))
        ref.status = CourseReferral.Status.SUCCESS
        ref.sale_amount = sale_amount
        ref.commission_amount = commission
        ref.commission_paid_at = timezone.now()
        ref.save(
            update_fields=[
                "status",
                "sale_amount",
                "commission_amount",
                "commission_paid_at",
            ]
        )
        ref.referrer.add_wallet(
            commission,
            transaction_type="EARN_REFERRAL",
            reference_id=f"course_ref:{ref.id}",
        )


def complete_course_order_after_payment(
    order: CourseOrder,
    user,
    payment_id: str | None,
    signature: str | None,
    request,
) -> None:
    # `order.lines` contains CourseOrderLine rows; convert to Course objects for purchase + referral logic.
    lines = list(order.lines.select_related("course"))
    courses = [line.course for line in lines]
    paid_unit_prices = {line.course_id: line.unit_price_inr for line in lines}
    with transaction.atomic():
        order.razorpay_payment_id = payment_id or ""
        order.razorpay_signature = signature or ""
        order.status = CourseOrder.Status.SUCCESS
        order.save(
            update_fields=["razorpay_payment_id", "razorpay_signature", "status"],
        )
        for c in courses:
            CoursePurchase.objects.get_or_create(
                user=user,
                course=c,
                defaults={"order": order},
            )
    # Auto-enroll the buyer into whichever LMS batch delivers this catalog course, if any
    # tutor/faculty has been assigned to teach it yet (see lms.LmsCourse.catalog_course).
    from lms import services as lms_services

    for c in courses:
        lms_services.enroll_from_catalog_purchase(user, c)
    finalize_referral_commissions(user, courses, paid_unit_prices=paid_unit_prices)
    clear_cart(request)


def create_course_checkout_order(user, courses: list[Course]):
    """
    Create Razorpay order + DB CourseOrder + lines. Returns dict for JsonResponse or raises nothing (caller handles).

    For dummy mode / misconfiguration returns tuple for JsonResponse construction by caller.
    """
    lines_payload = [(c, unit_checkout_price_inr(c, user)) for c in courses]
    total_inr = sum((p for _, p in lines_payload), Decimal("0"))
    amount_paise = int(total_inr * 100)

    if razorpay_dummy_mode():
        rid = make_dummy_order_id()
        order = CourseOrder.objects.create(
            user=user,
            total_inr=total_inr,
            razorpay_order_id=rid,
            status=CourseOrder.Status.PENDING,
        )
        for c, price in lines_payload:
            CourseOrderLine.objects.create(order=order, course=c, unit_price_inr=price)
        return {
            "checkout_mode": "dummy",
            "order_id": rid,
            "amount": amount_paise,
            "currency": "INR",
            "key": "rzp_test_DUMMYLOCAL",
            "description": _checkout_description(courses),
        }

    client = get_razorpay_client()
    if not client:
        return {"error": "Razorpay is not configured.", "http_status": 400}

    if amount_paise < 100:
        return {
            "error": "Cart total must be at least ₹1 (100 paise) for card/UPI checkout.",
            "http_status": 400,
        }

    receipt = f"c_{uuid.uuid4().hex}"[:40]
    order_data = {
        "amount": amount_paise,
        "currency": "INR",
        "receipt": receipt,
        "payment_capture": "1",
    }
    try:
        rz_order = client.order.create(data=order_data)
    except rz_errors.BadRequestError as e:
        msg = str(e)
        lower = msg.lower()
        if any(w in lower for w in ("authentication", "credential", "unauthorized", "not authorised")):
            return {"error": msg, "http_status": 401}
        return {"error": msg, "http_status": 400}
    except (rz_errors.GatewayError, rz_errors.ServerError) as e:
        return {"error": str(e), "http_status": 500}

    order = CourseOrder.objects.create(
        user=user,
        total_inr=total_inr,
        razorpay_order_id=rz_order["id"],
        status=CourseOrder.Status.PENDING,
    )
    for c, price in lines_payload:
        CourseOrderLine.objects.create(order=order, course=c, unit_price_inr=price)

    return {
        "checkout_mode": "live",
        "order_id": rz_order["id"],
        "amount": amount_paise,
        "currency": rz_order.get("currency", "INR"),
        "key": settings.RAZORPAY_KEY_ID,
        "description": _checkout_description(courses),
    }


def _checkout_description(courses: list[Course]) -> str:
    if len(courses) == 1:
        return courses[0].title
    return f"RankJee courses ({len(courses)} items)"


def complete_free_checkout(user, courses: list[Course], request):
    """Grant access when total is ₹0 without calling Razorpay."""
    rid = f"ord_free_{uuid.uuid4().hex}"[:99]
    lines_payload = [(c, unit_checkout_price_inr(c, user)) for c in courses]
    total_inr = sum((p for _, p in lines_payload), Decimal("0"))
    order = CourseOrder.objects.create(
        user=user,
        total_inr=total_inr,
        razorpay_order_id=rid,
        status=CourseOrder.Status.PENDING,
    )
    for c, unit_inr in lines_payload:
        CourseOrderLine.objects.create(
            order=order,
            course=c,
            unit_price_inr=unit_inr,
        )
    complete_course_order_after_payment(order, user, "free", "na", request)
    return order
