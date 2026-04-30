from urllib.parse import urlparse

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Sync django.contrib.sites current Site domain/name from SITE_BASE_URL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--site-id",
            type=int,
            default=None,
            help="Optional Site ID override. Defaults to settings.SITE_ID.",
        )
        parser.add_argument(
            "--domain",
            default="",
            help="Optional explicit domain override (e.g. rankjee.com).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print intended changes without saving.",
        )

    def handle(self, *args, **options):
        site_id = options["site_id"] or getattr(settings, "SITE_ID", 1)
        explicit_domain = (options["domain"] or "").strip()

        if explicit_domain:
            domain = explicit_domain
        else:
            base_url = (getattr(settings, "SITE_BASE_URL", "") or "").strip()
            if not base_url:
                self.stderr.write(self.style.ERROR("SITE_BASE_URL is empty. Pass --domain or set SITE_BASE_URL."))
                return
            parsed = urlparse(base_url if "://" in base_url else f"https://{base_url}")
            domain = (parsed.netloc or parsed.path or "").strip()

        if not domain:
            self.stderr.write(self.style.ERROR("Could not resolve a valid domain."))
            return

        site = Site.objects.filter(pk=site_id).first()
        if not site:
            self.stderr.write(self.style.ERROR(f"Site with id={site_id} not found."))
            return

        old_domain = site.domain
        old_name = site.name

        self.stdout.write(f"Target Site ID: {site_id}")
        self.stdout.write(f"Old domain/name: {old_domain} / {old_name}")
        self.stdout.write(f"New domain/name: {domain} / {domain}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run only. No changes saved."))
            return

        site.domain = domain
        site.name = domain
        site.save(update_fields=["domain", "name"])
        self.stdout.write(self.style.SUCCESS("Site domain/name updated successfully."))
