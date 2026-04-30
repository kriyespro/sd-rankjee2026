from django.contrib import admin
from .models import SeoTarget, StudentDailyClassLog


@admin.register(StudentDailyClassLog)
class StudentDailyClassLogAdmin(admin.ModelAdmin):
    list_display = ("log_date", "user", "topic", "attendance", "created_at")
    list_filter = ("attendance", "log_date")
    search_fields = ("topic", "details", "user__username", "user__email")
    autocomplete_fields = ("user",)
    date_hierarchy = "log_date"


@admin.register(SeoTarget)
class SeoTargetAdmin(admin.ModelAdmin):
    list_display = ("title", "phase", "status", "priority", "due_date", "owner", "updated_at")
    list_filter = ("status", "priority", "phase")
    search_fields = ("title", "phase", "owner", "notes")
    ordering = ("sort_order", "id")
