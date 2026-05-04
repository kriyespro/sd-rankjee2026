"""Verify Razorpay REST credentials without printing secrets (run on server after deploy)."""

from django.conf import settings
from django.core.management.base import BaseCommand

from payments.services import get_razorpay_client, razorpay_dummy_mode


class Command(BaseCommand):
    help = "Test Razorpay API authentication (KEY_ID + KEY_SECRET). Secrets are never printed."

    def handle(self, *args, **options):
        kid = getattr(settings, "RAZORPAY_KEY_ID", "") or ""
        sec_set = bool(getattr(settings, "RAZORPAY_KEY_SECRET", ""))

        self.stdout.write(f"razorpay_dummy_mode: {razorpay_dummy_mode()}")
        self.stdout.write(f"RAZORPAY_KEY_ID length: {len(kid)} prefix: {kid[:14]}…" if len(kid) > 14 else f"RAZORPAY_KEY_ID: {kid!r}")
        self.stdout.write(f"RAZORPAY_KEY_SECRET set: {sec_set}")

        if razorpay_dummy_mode():
            self.stdout.write(self.style.WARNING("Dummy checkout active — real Razorpay API is skipped."))
            return

        if not kid or not sec_set:
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
            self.stdout.write("Fix: Regenerate API secret in Razorpay Dashboard → copy both Key Id and Key Secret again (no quotes in .env).")
            return

        self.stdout.write(self.style.SUCCESS("Razorpay API authentication OK (list orders)."))
