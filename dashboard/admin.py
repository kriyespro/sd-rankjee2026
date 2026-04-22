from django.contrib import admin
from .models import SeoTarget


@admin.register(SeoTarget)
class SeoTargetAdmin(admin.ModelAdmin):
    list_display = ("title", "phase", "status", "priority", "due_date", "owner", "updated_at")
    list_filter = ("status", "priority", "phase")
    search_fields = ("title", "phase", "owner", "notes")
    ordering = ("sort_order", "id")
