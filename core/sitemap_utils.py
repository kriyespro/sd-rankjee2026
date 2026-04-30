from types import SimpleNamespace
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.sitemaps import Sitemap


class CanonicalHostSitemap(Sitemap):
    """
    Force sitemap host/protocol from SITE_BASE_URL so production output does not
    depend on Sites table defaults (which can be example.com).
    """

    def get_urls(self, page=1, site=None, protocol=None):
        base_url = (getattr(settings, "SITE_BASE_URL", "") or "").strip()
        parsed = urlparse(base_url if "://" in base_url else f"https://{base_url}")
        host = (parsed.netloc or parsed.path or "").strip()
        forced_protocol = (parsed.scheme or "https").strip().lower()

        if host:
            site = SimpleNamespace(domain=host, name=host)
        protocol = protocol or forced_protocol
        return super().get_urls(page=page, site=site, protocol=protocol)
