from django.contrib import admin

from .models import (
    ServerBuyMessageConfig,
    ServerOrderDetail,
    ServerPackage,
    StudentServerOrder,
)


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


@admin.register(ServerOrderDetail)
class ServerOrderDetailAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "order_user", "order_status", "updated_at")
    search_fields = (
        "order__razorpay_order_id",
        "order__domain_name",
        "order__user__username",
        "order__user__email",
        "server_ip",
        "panel_url",
    )
    autocomplete_fields = ("order",)
    readonly_fields = ("updated_at",)
    fieldsets = (
        (
            "Order link",
            {
                "fields": ("order",),
            },
        ),
        (
            "Student-visible status",
            {
                "fields": ("status_message",),
                "description": (
                    "If empty, student sees: "
                    "'Your order is in process. Please wait up to 4 hours.'"
                ),
            },
        ),
        (
            "Server details",
            {
                "fields": (
                    "server_ip",
                    "panel_url",
                    "login_username",
                    "login_password",
                    "nameservers",
                    "extra_details",
                ),
            },
        ),
        (
            "System",
            {
                "classes": ("collapse",),
                "fields": ("updated_at",),
            },
        ),
    )

    @admin.display(description="Student")
    def order_user(self, obj):
        return obj.order.user

    @admin.display(description="Order status")
    def order_status(self, obj):
        return obj.order.status


@admin.register(ServerBuyMessageConfig)
class ServerBuyMessageConfigAdmin(admin.ModelAdmin):
    list_display = ("key", "updated_at")
    readonly_fields = ("key", "updated_at")
    fieldsets = (
        (
            "Success message editor",
            {
                "fields": ("success_message",),
                "description": (
                    "This custom text appears on student dashboard after successful "
                    "server-buy payment."
                ),
            },
        ),
        (
            "System",
            {
                "classes": ("collapse",),
                "fields": ("key", "updated_at"),
            },
        ),
    )

    def has_add_permission(self, request):
        if not request.user.is_superuser:
            return False
        return not ServerBuyMessageConfig.objects.exists()
