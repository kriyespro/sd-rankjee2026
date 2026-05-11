from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.core.exceptions import ValidationError

from .models import ServerPackage

Q2 = Decimal("0.01")


def _quantize_inr(value: Decimal) -> Decimal:
    return value.quantize(Q2, rounding=ROUND_HALF_UP)


def quote_for_package_id(package_id) -> dict[str, Any]:
    """Build display + payment payload from a single ServerPackage row."""
    if not package_id:
        raise ValidationError("Choose a server setup.")
    try:
        pk = int(package_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Invalid server setup.") from exc

    pkg = ServerPackage.objects.filter(pk=pk, is_active=True).first()
    if not pkg:
        raise ValidationError("That server setup is not available.")

    total = _quantize_inr(pkg.price_inr)
    snapshot = {
        "package_id": pkg.id,
        "title": pkg.title,
        "ram_spec": pkg.ram_spec,
        "cpu_spec": pkg.cpu_spec,
        "ssd_spec": pkg.ssd_spec,
        "location": pkg.location,
        "duration_months": pkg.duration_months,
        "price_inr": str(total),
    }
    lines = [
        {"label": "RAM", "value": pkg.ram_spec, "kind": "spec"},
        {"label": "CPU", "value": pkg.cpu_spec, "kind": "spec"},
        {"label": "SSD", "value": pkg.ssd_spec, "kind": "spec"},
        {"label": "Location", "value": pkg.get_location_display(), "kind": "spec"},
        {
            "label": "Duration",
            "value": pkg.get_duration_months_display(),
            "kind": "spec",
        },
    ]

    return {
        "package_id": pkg.id,
        "title": pkg.title,
        "total_inr": total,
        "lines": lines,
        "duration_months": pkg.duration_months,
        "location": pkg.location,
        "snapshot": snapshot,
    }
