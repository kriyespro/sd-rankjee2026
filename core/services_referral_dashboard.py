"""Referral link click logging and earnings dashboard aggregates."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.utils import timezone

from .models import CourseReferral, ReferralLinkClick
from .services_course_checkout import (
    REFERRAL_COMMISSION_PERCENT_DEFAULT,
    _quantize_inr,
    expected_referral_sale_amount_inr,
)


def log_referral_click(request, ref_code: str, course=None) -> None:
    """Record one visit per session + path + day (skip self-clicks)."""
    ref_code = (ref_code or "").strip().upper()
    if not ref_code:
        return

    User = get_user_model()
    referrer = User.objects.filter(referral_code=ref_code).only("id").first()
    if not referrer:
        return

    if request.user.is_authenticated and request.user.id == referrer.id:
        return

    if not request.session.session_key:
        request.session.save()

    path = (request.path or "")[:200]
    session_key = (request.session.session_key or "")[:40]
    today = timezone.localdate()

    exists = ReferralLinkClick.objects.filter(
        referrer_id=referrer.id,
        session_key=session_key,
        path=path,
        course=course,
        created_at__date=today,
    ).exists()
    if exists:
        return

    ReferralLinkClick.objects.create(
        referrer_id=referrer.id,
        course=course,
        path=path,
        session_key=session_key,
    )


def referral_dashboard_stats(user) -> dict:
    """Smart referral funnel stats for the earnings page."""
    now = timezone.now()
    since_7d = now - timedelta(days=7)
    since_30d = now - timedelta(days=30)

    clicks_qs = ReferralLinkClick.objects.filter(referrer=user)
    clicks_all = clicks_qs.count()
    clicks_7d = clicks_qs.filter(created_at__gte=since_7d).count()
    clicks_30d = clicks_qs.filter(created_at__gte=since_30d).count()

    referrals_qs = CourseReferral.objects.filter(referrer=user).select_related("course")
    leads_total = referrals_qs.count()
    unique_emails = referrals_qs.values("lead_email").distinct().count()

    pending_qs = referrals_qs.filter(status=CourseReferral.Status.PENDING)
    pending_n = pending_qs.count()

    success_qs = referrals_qs.filter(status=CourseReferral.Status.SUCCESS)
    success_n = success_qs.count()
    earned_total = success_qs.aggregate(total=Sum("commission_amount"))["total"] or Decimal("0")

    predicted_pending = Decimal("0")
    for ref in pending_qs:
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
        referrals_qs.order_by("-created_at")[:6].values(
            "lead_email",
            "lead_name",
            "status",
            "course__title",
            "created_at",
            "commission_amount",
        )
    )

    top_courses = list(
        referrals_qs.values("course__title")
        .annotate(n=Count("id"))
        .order_by("-n")[:3]
    )

    return {
        "clicks_all": clicks_all,
        "clicks_7d": clicks_7d,
        "clicks_30d": clicks_30d,
        "leads_total": leads_total,
        "unique_emails": unique_emails,
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
