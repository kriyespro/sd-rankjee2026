# Generated manually — example presets after package model introduction

from decimal import Decimal

from django.db import migrations


def seed_packages(apps, schema_editor):
    ServerPackage = apps.get_model("server_buy", "ServerPackage")
    if ServerPackage.objects.exists():
        return

    samples = [
        {
            "title": "Starter — India — 1 year",
            "ram_spec": "4 GB",
            "cpu_spec": "2 vCPU",
            "ssd_spec": "128 GB SSD",
            "location": "INDIA",
            "duration_months": 12,
            "price_inr": Decimal("33600"),
            "sort_order": 10,
        },
        {
            "title": "Growth — India — 2 years",
            "ram_spec": "8 GB",
            "cpu_spec": "4 vCPU",
            "ssd_spec": "256 GB SSD",
            "location": "INDIA",
            "duration_months": 24,
            "price_inr": Decimal("165000"),
            "sort_order": 20,
        },
        {
            "title": "Performance — USA — 1 year",
            "ram_spec": "16 GB",
            "cpu_spec": "8 vCPU",
            "ssd_spec": "512 GB SSD",
            "location": "USA",
            "duration_months": 12,
            "price_inr": Decimal("285000"),
            "sort_order": 30,
        },
    ]
    for row in samples:
        ServerPackage.objects.create(
            title=row["title"],
            ram_spec=row["ram_spec"],
            cpu_spec=row["cpu_spec"],
            ssd_spec=row["ssd_spec"],
            location=row["location"],
            duration_months=row["duration_months"],
            price_inr=row["price_inr"],
            sort_order=row["sort_order"],
            is_active=True,
            notes="",
        )


def unseed_packages(apps, schema_editor):
    ServerPackage = apps.get_model("server_buy", "ServerPackage")
    ServerPackage.objects.filter(
        title__in=[
            "Starter — India — 1 year",
            "Growth — India — 2 years",
            "Performance — USA — 1 year",
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("server_buy", "0003_server_packages"),
    ]

    operations = [
        migrations.RunPython(seed_packages, unseed_packages),
    ]
