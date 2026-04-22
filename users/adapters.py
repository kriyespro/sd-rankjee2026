from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.urls import reverse


class RoleAwareSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Route new social users through role onboarding before dashboard."""

    def get_login_redirect_url(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and not getattr(user, "onboarding_completed", True):
            return reverse("users:onboarding_role")
        return reverse("dashboard:index")
