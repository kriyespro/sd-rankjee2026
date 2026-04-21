import logging

from allauth.account.signals import user_signed_up

from django.dispatch import receiver

from .subscription import try_apply_signup_pro_trial

logger = logging.getLogger("rankjee.signup")


@receiver(user_signed_up)
def on_allauth_user_signed_up(request, user, **kwargs):
    """OAuth / allauth signups skip users.views.signup_view — apply the same one-time Pro trial."""
    try:
        try_apply_signup_pro_trial(user)
    except Exception as exc:
        logger.warning(
            "Signup Pro trial failed for user_id=%s: %s",
            getattr(user, "pk", None),
            exc,
            exc_info=True,
        )
