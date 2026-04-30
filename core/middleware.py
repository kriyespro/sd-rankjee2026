from django.conf import settings
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

        # Keep the original path/query and force the canonical https origin.
        return HttpResponsePermanentRedirect(
            f"https://{canonical_host}{request.get_full_path()}"
        )
