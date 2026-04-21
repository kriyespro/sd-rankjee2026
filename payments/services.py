"""Razorpay helpers: real API vs local dummy checkout (no gateway keys)."""
import os
import uuid
from datetime import timedelta

from django.conf import settings
from django.utils import timezone


def razorpay_dummy_mode() -> bool:
    """Simulated checkout when RAZORPAY_USE_DUMMY=1 or DEBUG with missing keys."""
    if os.environ.get("RAZORPAY_USE_DUMMY", "").lower() in ("1", "true", "yes"):
        return True
    if settings.DEBUG and (
        not getattr(settings, "RAZORPAY_KEY_ID", "")
        or not getattr(settings, "RAZORPAY_KEY_SECRET", "")
    ):
        return True
    return False


def make_dummy_order_id() -> str:
    return f"ord_dummy_{uuid.uuid4().hex}"


def get_razorpay_client():
    """Return Client or None when using dummy checkout."""
    if razorpay_dummy_mode():
        return None
    import razorpay

    return razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )


def _complimentary_subscription_plan():
    """Plan row used for admin grants, signup trial, referral unlocks (duration comes from end_date)."""
    from payments.models import SubscriptionPlan

    trial_plan = SubscriptionPlan.objects.filter(is_active=True).order_by("price").first()
    if trial_plan:
        return trial_plan
    trial_plan = SubscriptionPlan.objects.filter(name="Complimentary Pro Access").order_by("-id").first()
    if trial_plan:
        return trial_plan
    return SubscriptionPlan.objects.create(
        name="Complimentary Pro Access",
        description="Internal complimentary access (signup trial, admin grants, testers).",
        price=0,
        duration_days=30,
        is_active=False,
        features=["Complimentary Pro access"],
    )


def grant_complimentary_subscription_days(user, days):
    """
    Add ``days`` to the user's exam Pro subscription window (payments module).
    Extension starts from max(now, current end_date). Idempotent with respect to
    paid upgrades: later paid orders replace plan and extend from their own rules.
    """
    from payments.models import UserSubscription

    if days <= 0:
        return
    plan = _complimentary_subscription_plan()
    now = timezone.now()
    sub, created = UserSubscription.objects.get_or_create(
        user=user,
        defaults={
            "plan": plan,
            "end_date": now + timedelta(days=days),
            "is_active": True,
        },
    )
    if not created:
        base = sub.end_date if sub.end_date and sub.end_date > now else now
        sub.plan = plan
        sub.end_date = base + timedelta(days=days)
        sub.is_active = True
        sub.save(update_fields=["plan", "end_date", "is_active"])
