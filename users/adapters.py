from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.urls import reverse

from .onboarding import incomplete_onboarding_url_name


class RoleAwareSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Route new social users through onboarding (role once if needed, then profile)."""

    def get_login_redirect_url(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and not getattr(user, "onboarding_completed", True):
            return reverse(incomplete_onboarding_url_name(request))
        return reverse("dashboard:index")
