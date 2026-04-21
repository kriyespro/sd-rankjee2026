from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .gamification import on_referral_signup
from .models import CustomUser


def process_referral_signup(user, referral_code: str) -> bool:
    """
    Apply referral linking/reward for a newly created user.
    Returns True when a valid referrer was applied.
    """
    ref_code = (referral_code or "").strip().upper()
    if not ref_code:
        return False

    try:
        referrer = CustomUser.objects.get(referral_code=ref_code)
    except CustomUser.DoesNotExist:
        return False

    if referrer == user:
        return False

    # Idempotent guard: skip if already linked.
    if user.referred_by_id:
        return True

    user.referred_by = referrer
    user.save(update_fields=["referred_by"])
    on_referral_signup(user, referrer)

    if settings.REFERRAL_PREMIUM_ENABLED:
        from payments.models import SubscriptionPlan, UserSubscription

        trial_plan = SubscriptionPlan.objects.filter(is_active=True).order_by("price").first()
        if not trial_plan:
            trial_plan = SubscriptionPlan.objects.filter(name="Referral Test Pro").order_by("-id").first()
        if not trial_plan:
            trial_plan = SubscriptionPlan.objects.create(
                name="Referral Test Pro",
                description="Auto-created zero-price plan for referral testing unlocks.",
                price=0,
                duration_days=max(1, int(settings.REFERRAL_PREMIUM_DAYS)),
                is_active=False,
                features=["Referral test premium access"],
            )
        if trial_plan:
            sub, created = UserSubscription.objects.get_or_create(
                user=user,
                defaults={
                    "plan": trial_plan,
                    "end_date": timezone.now() + timedelta(days=settings.REFERRAL_PREMIUM_DAYS),
                    "is_active": True,
                },
            )
            if not created:
                base = sub.end_date if sub.end_date and sub.end_date > timezone.now() else timezone.now()
                sub.plan = trial_plan
                sub.end_date = base + timedelta(days=settings.REFERRAL_PREMIUM_DAYS)
                sub.is_active = True
                sub.save(update_fields=["plan", "end_date", "is_active"])

    return True

