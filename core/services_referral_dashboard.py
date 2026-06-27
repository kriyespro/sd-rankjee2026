"""Referral link click logging and earnings dashboard aggregates."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.utils import timezone

from .models import CourseReferral, ReferralLinkClick
from .services_course_checkout import (
    REFERRAL_COMMISSION_PERCENT_DEFAULT,
    _quantize_inr,
    expected_referral_sale_amount_inr,
)

_REFERRER_ID_CACHE_TTL = 300
_DASHBOARD_CACHE_TTL = 45


def _referrer_id_for_code(ref_code: str) -> int | None:
    cache_key = f"ref_uid:{ref_code}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached or None

    User = get_user_model()
    referrer_id = (
        User.objects.filter(referral_code=ref_code).values_list("id", flat=True).first()
    )
    cache.set(cache_key, referrer_id or 0, _REFERRER_ID_CACHE_TTL)
    return referrer_id


def log_referral_click(request, ref_code: str, course=None) -> None:
    """Record one visit per session + path + day (skip self-clicks)."""
    ref_code = (ref_code or "").strip().upper()
    if not ref_code:
        return

    referrer_id = _referrer_id_for_code(ref_code)
    if not referrer_id:
        return

    if request.user.is_authenticated and request.user.id == referrer_id:
        return

    if not request.session.session_key:
        request.session.save()

    path = (request.path or "")[:200]
    course_id = course.pk if course is not None else 0
    today = timezone.localdate().isoformat()
    session_flag = f"rclk:{referrer_id}:{path}:{course_id}:{today}"
    if request.session.get(session_flag):
        return

    ReferralLinkClick.objects.create(
        referrer_id=referrer_id,
        course=course,
        path=path,
        session_key=(request.session.session_key or "")[:40],
    )
    request.session[session_flag] = True


def referral_dashboard_stats(user, *, use_cache: bool = True) -> dict:
    """Smart referral funnel stats for the earnings page (few DB round-trips)."""
    if use_cache:
        cache_key = f"referral_dash:{user.pk}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    now = timezone.now()
    since_7d = now - timedelta(days=7)
    since_30d = now - timedelta(days=30)

    click_agg = ReferralLinkClick.objects.filter(referrer=user).aggregate(
        clicks_all=Count("id"),
        clicks_7d=Count("id", filter=Q(created_at__gte=since_7d)),
        clicks_30d=Count("id", filter=Q(created_at__gte=since_30d)),
    )

    ref_agg = CourseReferral.objects.filter(referrer=user).aggregate(
        leads_total=Count("id"),
        unique_emails=Count("lead_email", distinct=True),
        pending_n=Count("id", filter=Q(status=CourseReferral.Status.PENDING)),
        success_n=Count("id", filter=Q(status=CourseReferral.Status.SUCCESS)),
        earned_total=Sum(
            "commission_amount",
            filter=Q(status=CourseReferral.Status.SUCCESS),
        ),
    )

    leads_total = ref_agg["leads_total"] or 0
    pending_n = ref_agg["pending_n"] or 0
    success_n = ref_agg["success_n"] or 0
    clicks_all = click_agg["clicks_all"] or 0
    earned_total = ref_agg["earned_total"] or Decimal("0")

    predicted_pending = Decimal("0")
    if pending_n:
        pending_refs = CourseReferral.objects.filter(
            referrer=user,
            status=CourseReferral.Status.PENDING,
        ).select_related("course").only(
            "sale_amount",
            "commission_percent",
            "course__price_inr",
        )
        for ref in pending_refs:
            sale = ref.sale_amount or expected_referral_sale_amount_inr(ref.course)
            pct = ref.commission_percent or REFERRAL_COMMISSION_PERCENT_DEFAULT
            predicted_pending += sale * pct / Decimal("100")
    predicted_pending = _quantize_inr(predicted_pending)

    User = get_user_model()
    signup_referrals = User.objects.filter(referred_by=user).count()
    signup_referral_users = list(
        User.objects.filter(referred_by=user)
        .order_by("-date_joined")[:25]
        .values("email", "username", "date_joined", "is_active")
    )
    for row in signup_referral_users:
        row["status_label"] = "Active" if row["is_active"] else "Inactive"

    lead_rate = round(leads_total / clicks_all * 100, 1) if clicks_all else None
    pay_rate = round(success_n / leads_total * 100, 1) if leads_total else None
    click_to_pay = round(success_n / clicks_all * 100, 1) if clicks_all else None
    avg_commission = _quantize_inr(earned_total / success_n) if success_n else Decimal("0")

    recent_leads = list(
        CourseReferral.objects.filter(referrer=user)
        .order_by("-created_at")[:6]
        .values(
            "lead_email",
            "lead_name",
            "status",
            "course__title",
            "created_at",
            "commission_amount",
        )
    )

    top_courses = list(
        CourseReferral.objects.filter(referrer=user)
        .values("course__title")
        .annotate(n=Count("id"))
        .order_by("-n")[:3]
    )

    result = {
        "clicks_all": clicks_all,
        "clicks_7d": click_agg["clicks_7d"] or 0,
        "clicks_30d": click_agg["clicks_30d"] or 0,
        "leads_total": leads_total,
        "unique_emails": ref_agg["unique_emails"] or 0,
        "pending_n": pending_n,
        "success_n": success_n,
        "earned_total": earned_total,
        "predicted_pending": predicted_pending,
        "signup_referrals": signup_referrals,
        "signup_referral_users": signup_referral_users,
        "lead_rate": lead_rate,
        "pay_rate": pay_rate,
        "click_to_pay": click_to_pay,
        "avg_commission": avg_commission,
        "recent_leads": recent_leads,
        "top_courses": top_courses,
    }

    if use_cache:
        cache.set(f"referral_dash:{user.pk}", result, _DASHBOARD_CACHE_TTL)

    return result


def invalidate_referral_dashboard_cache(user_id: int) -> None:
    cache.delete(f"referral_dash:{user_id}")
