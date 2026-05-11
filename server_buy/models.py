from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class ServerPackage(models.Model):
    """
    One admin row = one sellable server setup: specs + duration + fixed checkout price.
    Students pick a package on the buy page; no formula is applied at checkout.
    """

    class Location(models.TextChoices):
        INDIA = "INDIA", "India"
        USA = "USA", "USA"

    class DurationMonths(models.IntegerChoices):
        ONE_YEAR = 12, "1 year"
        TWO_YEARS = 24, "2 years"
        THREE_YEARS = 36, "3 years"

    title = models.CharField(
        max_length=120,
        help_text="Short name shown in the list, e.g. Pro — India — 2 years.",
    )
    ram_spec = models.CharField(max_length=80, help_text="e.g. 8 GB")
    cpu_spec = models.CharField(max_length=80, help_text="e.g. 4 vCPU")
    ssd_spec = models.CharField(max_length=80, help_text="e.g. 256 GB SSD")
    location = models.CharField(max_length=20, choices=Location.choices, db_index=True)
    duration_months = models.PositiveSmallIntegerField(
        choices=DurationMonths.choices,
        default=DurationMonths.ONE_YEAR,
        help_text="Billing period for this fixed price.",
    )
    price_inr = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("1"))],
        help_text="Total amount the student pays (one Razorpay charge).",
    )
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    notes = models.TextField(
        blank=True,
        help_text="Internal only — not shown on the buy page.",
    )

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = "Server package"
        verbose_name_plural = "Server packages"

    def __str__(self):
        return self.title


class StudentServerOrder(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESS = "SUCCESS", "Paid"
        FAILED = "FAILED", "Failed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="server_buy_orders",
    )
    domain_name = models.CharField(max_length=255)
    package = models.ForeignKey(
        ServerPackage,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )
    total_inr = models.DecimalField(max_digits=14, decimal_places=2)
    pricing_snapshot = models.JSONField(default=dict, blank=True)
    razorpay_order_id = models.CharField(max_length=100, unique=True, db_index=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=200, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Server order {self.razorpay_order_id} — {self.status} ₹{self.total_inr}"
