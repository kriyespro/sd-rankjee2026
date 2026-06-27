from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponsePermanentRedirect


class CanonicalHostRedirectMiddleware:
    """
    Redirect all non-canonical hosts to the configured canonical host.

    This keeps OAuth callback host/scheme stable across www/non-www and
    prevents redirect_uri_mismatch for social logins.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "CANONICAL_HOST_REDIRECT_ENABLED", False):
            return self.get_response(request)

        canonical_host = (getattr(settings, "CANONICAL_HOST", "") or "").strip().lower()
        if not canonical_host:
            return self.get_response(request)

        request_host = request.get_host().split(":", 1)[0].strip().lower()
        if not request_host or request_host == canonical_host:
            return self.get_response(request)

        return HttpResponsePermanentRedirect(
            f"https://{canonical_host}{request.get_full_path()}"
        )


class UserPremiumMiddleware:
    """Cache exam-Pro status per request (and Redis) — avoids subscription query on every page."""

    _CACHE_TTL = 120

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            user._cached_is_premium = self._resolve_premium(user)
        return self.get_response(request)

    def _resolve_premium(self, user) -> bool:
        from users.models import CustomUser

        if getattr(user, "role", None) == CustomUser.Role.VIP_USER:
            return True
        if getattr(user, "is_vip_testing_user", False):
            return True

        cache_key = f"user_premium:{user.pk}"
        cached = cache.get(cache_key)
        if cached is not None:
            return bool(cached)

        premium = False
        try:
            sub = user.subscription
        except ObjectDoesNotExist:
            sub = None
        if sub and sub.is_active and not sub.is_expired:
            premium = True

        cache.set(cache_key, premium, self._CACHE_TTL)
        return premium


def invalidate_user_premium_cache(user_id: int) -> None:
    cache.delete(f"user_premium:{user_id}")
