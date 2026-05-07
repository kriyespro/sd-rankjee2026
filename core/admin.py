from decimal import Decimal

from django.contrib import admin
from django.utils import timezone

from .services_course_checkout import REFERRAL_COMMISSION_PERCENT_DEFAULT, unit_checkout_price_inr
from .models import (
    Course,
    CourseOrder,
    CourseOrderLine,
    CoursePurchase,
    CourseReferral,
    EarningTask,
    LegalPage,
    TutorLeadRequest,
    UserTaskSubmission,
)

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


class CourseOrderLineInline(admin.TabularInline):
    model = CourseOrderLine
    extra = 0
    raw_id_fields = ("course",)


@admin.register(CourseOrder)
class CourseOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "total_inr", "status", "razorpay_order_id", "created_at")
    list_filter = ("status",)
    search_fields = ("razorpay_order_id", "user__username", "user__email")
    raw_id_fields = ("user",)
    inlines = (CourseOrderLineInline,)


@admin.register(CoursePurchase)
class CoursePurchaseAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "order", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "course__title", "course__slug")
    raw_id_fields = ("user", "course", "order")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "price_inr", "duration_weeks", "level", "is_active", "is_featured")
    list_filter = ("is_active", "is_featured", "level")
    search_fields = ("title", "slug")
    prepopulated_fields = {"slug": ("title",)}


@admin.action(description="Mark selected referrals SUCCESS and pay commission (default 18%%)")
def mark_referral_success_and_pay(modeladmin, request, queryset):
    for item in queryset.select_related("referrer", "course"):
        if item.commission_paid_at:
            continue
        sale_amount = item.sale_amount
        if sale_amount is None:
            if item.lead_user_id:
                sale_amount = unit_checkout_price_inr(item.course, item.lead_user)
            else:
                sale_amount = item.course.price_inr or Decimal("0")
        percent = item.commission_percent or REFERRAL_COMMISSION_PERCENT_DEFAULT
        commission = (sale_amount * percent / Decimal("100")).quantize(Decimal("0.01"))
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


@admin.register(TutorLeadRequest)
class TutorLeadRequestAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "full_name",
        "requester_type",
        "phone",
        "city",
        "subjects",
        "budget_inr",
        "status",
    )
    list_filter = ("status", "requester_type", "city")
    search_fields = ("full_name", "phone", "email", "city", "area", "subjects")


@admin.register(LegalPage)
class LegalPageAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "is_published", "updated_at")
    list_filter = ("is_published", "slug")
    search_fields = ("title", "content", "seo_title", "seo_description")
