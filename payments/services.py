"""Razorpay helpers: real API vs local dummy checkout (no gateway keys)."""
import os
import uuid

from django.conf import settings


def razorpay_dummy_mode() -> bool:
    """Simulated checkout when RAZORPAY_USE_DUMMY=1 or DEBUG with missing keys."""
    if os.environ.get("RAZORPAY_USE_DUMMY", "").lower() in ("1", "true", "yes"):
        return True
    if settings.DEBUG and (
        not getattr(settings, "RAZORPAY_KEY_ID", "")
        or not getattr(settings, "RAZORPAY_KEY_SECRET", "")
    ):
        return True
    return False


def make_dummy_order_id() -> str:
    return f"ord_dummy_{uuid.uuid4().hex}"


def get_razorpay_client():
    """Return Client or None when using dummy checkout."""
    if razorpay_dummy_mode():
        return None
    import razorpay

    return razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )
