"""Signup and complimentary Pro access (exam / payments module)."""
from django.conf import settings
from django.db import transaction
from django.utils import timezone


def try_apply_signup_pro_trial(user):
    """
    One-time Pro trial for new accounts (email signup or allauth / social signup).
    Stacks with referral-based premium: run this before referral handling on email signup.
    """
    if not getattr(settings, "SIGNUP_TRIAL_ENABLED", True):
        return
    days = int(getattr(settings, "SIGNUP_TRIAL_DAYS", 7))
    if days <= 0:
        return

    from users.models import CustomUser

    with transaction.atomic():
        locked = CustomUser.objects.select_for_update().get(pk=user.pk)
        if locked.signup_pro_trial_applied_at is not None:
            return
        from payments.services import grant_complimentary_subscription_days

        grant_complimentary_subscription_days(locked, days)
        locked.signup_pro_trial_applied_at = timezone.now()
        locked.save(update_fields=["signup_pro_trial_applied_at"])
