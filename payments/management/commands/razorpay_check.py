"""Verify Razorpay REST credentials without printing secrets (run on server after deploy)."""

from django.conf import settings
from django.core.management.base import BaseCommand

from payments.services import get_razorpay_client, razorpay_dummy_mode


class Command(BaseCommand):
    help = "Test Razorpay API authentication (KEY_ID + KEY_SECRET). Secrets are never printed."

    def handle(self, *args, **options):
        kid = getattr(settings, "RAZORPAY_KEY_ID", "") or ""
        secret = getattr(settings, "RAZORPAY_KEY_SECRET", "") or ""

        self.stdout.write(f"razorpay_dummy_mode: {razorpay_dummy_mode()}")
        self.stdout.write(f"RAZORPAY_KEY_ID length: {len(kid)} prefix: {kid[:14]}…" if len(kid) > 14 else f"RAZORPAY_KEY_ID: {kid!r}")
        self.stdout.write(f"RAZORPAY_KEY_SECRET length: {len(secret)}")

        if any(ch.isspace() for ch in kid):
            self.stdout.write(self.style.ERROR("RAZORPAY_KEY_ID contains whitespace — fix `.env` line."))
            return
        if any(ch.isspace() for ch in secret):
            self.stdout.write(self.style.ERROR("RAZORPAY_KEY_SECRET contains whitespace/newline — use single line in `.env`."))
            return

        if razorpay_dummy_mode():
            self.stdout.write(self.style.WARNING("Dummy checkout active — real Razorpay API is skipped."))
            return

        if not kid or not secret:
            self.stdout.write(self.style.ERROR("Missing KEY_ID or KEY_SECRET — check `.env` / Docker env."))
            return

        mode = "live"
        if kid.startswith("rzp_test_"):
            mode = "test"
        elif kid.startswith("rzp_live_"):
            mode = "live"
        else:
            self.stdout.write(self.style.WARNING("KEY_ID does not start with rzp_test_ or rzp_live_ — verify copy from Dashboard."))

        self.stdout.write(f"Detected mode hint: {mode} (must match secret from same Dashboard mode)")

        client = get_razorpay_client()
        if not client:
            self.stdout.write(self.style.ERROR("get_razorpay_client() is None — keys empty after sanitization."))
            return

        try:
            client.order.all({"count": 1})
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Razorpay API rejected credentials: {exc}"))
            self.stdout.write(
                "Fix checklist:\n"
                "  1) Pull latest `docker-compose.yml` — Razorpay vars must use `env_file: .env` (not ${VAR} in compose).\n"
                "  2) Razorpay Dashboard → Test mode → Account & Settings → API Keys → Regenerate Key Secret.\n"
                "  3) Paste full Key Id + Key Secret into project `.env` (one line each; no quotes; avoid `$` eaten by old compose).\n"
                "  4) `docker compose up -d --force-recreate web celery celery-beat` then `razorpay_check` again.\n"
                "  5) Secret must match Key Id from the same regenerate/copy operation."
            )
            return

        self.stdout.write(self.style.SUCCESS("Razorpay API authentication OK (list orders)."))
