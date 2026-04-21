from django.contrib import admin
from django.utils import timezone

from .models import Course, CourseReferral, EarningTask, UserTaskSubmission

@admin.register(EarningTask)
class EarningTaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'reward_amount', 'required_skill', 'is_active')
    list_filter = ('is_active',)

@admin.register(UserTaskSubmission)
class UserTaskSubmissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'task', 'status', 'submitted_at')
    list_filter = ('status',)
    actions = ['approve', 'reject']

    def approve(self, request, queryset):
        queryset.update(status='APPROVED')
    approve.short_description = "Approve selected submissions"

    def reject(self, request, queryset):
        queryset.update(status='REJECTED')
    reject.short_description = "Reject selected submissions"


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "price_inr", "duration_weeks", "level", "is_active", "is_featured")
    list_filter = ("is_active", "is_featured", "level")
    search_fields = ("title", "slug")
    prepopulated_fields = {"slug": ("title",)}


@admin.action(description="Mark selected referrals SUCCESS and pay 30%% commission")
def mark_referral_success_and_pay(modeladmin, request, queryset):
    for item in queryset.select_related("referrer", "course"):
        if item.commission_paid_at:
            continue
        sale_amount = item.sale_amount or item.course.price_inr or 0
        percent = item.commission_percent or 30
        commission = (sale_amount * percent) / 100
        item.status = CourseReferral.Status.SUCCESS
        item.sale_amount = sale_amount
        item.commission_amount = commission
        item.commission_paid_at = timezone.now()
        item.save(
            update_fields=[
                "status",
                "sale_amount",
                "commission_amount",
                "commission_paid_at",
            ]
        )
        item.referrer.add_wallet(
            commission,
            transaction_type="EARN_REFERRAL",
            reference_id=f"course_ref:{item.id}",
        )


@admin.action(description="Mark selected referrals as REJECTED")
def mark_referral_rejected(modeladmin, request, queryset):
    queryset.update(status=CourseReferral.Status.REJECTED)


@admin.register(CourseReferral)
class CourseReferralAdmin(admin.ModelAdmin):
    list_display = (
        "course",
        "referrer",
        "lead_email",
        "status",
        "sale_amount",
        "commission_amount",
        "commission_paid_at",
        "created_at",
    )
    list_filter = ("status", "course", "commission_paid_at")
    search_fields = ("lead_email", "lead_name", "referrer__username", "referrer__email")
    actions = (mark_referral_success_and_pay, mark_referral_rejected)
