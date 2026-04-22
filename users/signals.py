import logging

from allauth.account.signals import user_signed_up

from django.dispatch import receiver

from .referrals import process_referral_signup
from .subscription import try_apply_signup_pro_trial

logger = logging.getLogger("rankjee.signup")


@receiver(user_signed_up)
def on_allauth_user_signed_up(request, user, **kwargs):
    """OAuth / allauth signups skip users.views.signup_view — apply trial + pending referral code."""
    try:
        if getattr(user, "onboarding_completed", True):
            user.onboarding_completed = False
            user.save(update_fields=["onboarding_completed"])
        try_apply_signup_pro_trial(user)
        pending_code = ""
        if request and hasattr(request, "session"):
            pending_code = request.session.pop("pending_referral_code", "")
        if pending_code:
            process_referral_signup(user, pending_code)
    except Exception as exc:
        logger.warning(
            "Social signup post-processing failed for user_id=%s: %s",
            getattr(user, "pk", None),
            exc,
            exc_info=True,
        )
