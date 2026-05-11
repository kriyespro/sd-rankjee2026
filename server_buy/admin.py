from django.contrib import admin

from .models import ServerPackage, StudentServerOrder


@admin.register(ServerPackage)
class ServerPackageAdmin(admin.ModelAdmin):
    """One form row per preset: specs + duration + fixed price."""

    list_display = (
        "title",
        "ram_spec",
        "cpu_spec",
        "ssd_spec",
        "location",
        "duration_months",
        "price_inr",
        "is_active",
        "sort_order",
    )
    list_filter = ("is_active", "location", "duration_months")
    search_fields = ("title", "ram_spec", "cpu_spec", "ssd_spec", "notes")
    ordering = ("sort_order", "id")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "is_active",
                    "sort_order",
                )
            },
        ),
        (
            "Server setup (what the student sees)",
            {
                "fields": (
                    "ram_spec",
                    "cpu_spec",
                    "ssd_spec",
                    "location",
                    "duration_months",
                )
            },
        ),
        (
            "Pricing",
            {
                "fields": ("price_inr",),
                "description": "Fixed total for this setup (single Razorpay payment).",
            },
        ),
        (
            "Internal",
            {
                "classes": ("collapse",),
                "fields": ("notes",),
            },
        ),
    )


@admin.register(StudentServerOrder)
class StudentServerOrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "domain_name",
        "package",
        "total_inr",
        "status",
        "razorpay_order_id",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("domain_name", "razorpay_order_id", "user__username", "user__email")
    readonly_fields = ("created_at", "updated_at", "pricing_snapshot")
    raw_id_fields = ("user",)
    autocomplete_fields = ("package",)
