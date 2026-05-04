from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone

from .models import (
    Badge,
    CompanyInquiry,
    CustomUser,
    Notification,
    PublicProfile,
    UserBadge,
    WalletTransaction,
    WithdrawalRequest,
)
from .tasks import send_withdrawal_status_email
from .gamification import send_notification
from payments.services import grant_complimentary_subscription_days


@admin.action(description='Exam Pro: grant 30 days complimentary (payments plans access)')
def user_grant_30_days_pro(modeladmin, request, queryset):
    for user in queryset:
        grant_complimentary_subscription_days(user, 30)


@admin.action(description='Exam Pro: grant 7 days complimentary')
def user_grant_7_days_pro(modeladmin, request, queryset):
    for user in queryset:
        grant_complimentary_subscription_days(user, 7)


@admin.action(description='Mark selected users as VIP testing (always Pro for exam module)')
def user_mark_vip_testing(modeladmin, request, queryset):
    queryset.update(is_vip_testing_user=True)


@admin.action(description='Remove VIP testing flag from selected users')
def user_unmark_vip_testing(modeladmin, request, queryset):
    queryset.update(is_vip_testing_user=False)


@admin.action(description='Set selected users role to VIP_USER')
def user_set_role_vip_user(modeladmin, request, queryset):
    queryset.update(role=CustomUser.Role.VIP_USER)


@admin.action(description='Mark withdrawals as processed')
def withdrawal_mark_processed(modeladmin, request, queryset):
    now = timezone.now()
    for w in queryset.select_related("user"):
        if w.status == "PROCESSED":
            continue
        w.status = "PROCESSED"
        w.processed_at = now
        w.save(update_fields=["status", "processed_at"])
        send_notification(w.user, f"✅ Withdrawal processed: ₹{w.amount}", link="/earnings/")
        send_withdrawal_status_email.delay(w.id)


@admin.action(description='Mark withdrawals as rejected')
def withdrawal_mark_rejected(modeladmin, request, queryset):
    now = timezone.now()
    for w in queryset.select_related("user"):
        if w.status == "REJECTED":
            continue
        w.status = "REJECTED"
        w.processed_at = now
        w.save(update_fields=["status", "processed_at"])
        send_notification(w.user, f"❌ Withdrawal rejected: ₹{w.amount}", link="/earnings/")
        send_withdrawal_status_email.delay(w.id)


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'transaction_type', 'reference_id', 'created_at')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('user__username', 'user__email', 'reference_id')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'upi_id', 'status', 'requested_at', 'processed_at')
    list_filter = ('status', 'requested_at')
    search_fields = ('user__username', 'user__email', 'upi_id')
    readonly_fields = ('requested_at',)
    actions = (withdrawal_mark_processed, withdrawal_mark_rejected)
    date_hierarchy = 'requested_at'


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = (
        'username',
        'email',
        'role',
        'state',
        'is_vip_testing_user',
        'streak_days',
        'xp_points',
        'wallet_balance',
        'referral_code',
    )
    list_filter = (
        'role',
        'is_vip_testing_user',
        'state',
        'is_staff',
        'is_superuser',
        'is_active',
        'groups',
    )
    actions = UserAdmin.actions + (
        user_grant_30_days_pro,
        user_grant_7_days_pro,
        user_mark_vip_testing,
        user_unmark_vip_testing,
        user_set_role_vip_user,
    )
    readonly_fields = ('referral_code', 'last_ad_claim_at', 'signup_pro_trial_applied_at')
    fieldsets = UserAdmin.fieldsets + (
        (
            'RankJee',
            {
                'fields': (
                    'role',
                    'state',
                    'streak_days',
                    'xp_points',
                    'wallet_balance',
                    'last_active_date',
                    'last_ad_claim_at',
                    'referral_code',
                    'referred_by',
                )
            },
        ),
        (
            'Exam Pro (payments /plans)',
            {
                'fields': (
                    'is_vip_testing_user',
                    'signup_pro_trial_applied_at',
                ),
                'description': 'VIP testers always unlock exam Pro features. Use list actions to grant 7/30 day complimentary access (same as /payments/plans/).',
            },
        ),
    )


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ('badge_type', 'title', 'icon')


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ('user', 'badge', 'awarded_at')
    list_filter = ('badge',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'is_read', 'created_at')
    list_filter = ('is_read',)


@admin.register(PublicProfile)
class PublicProfileAdmin(admin.ModelAdmin):
    list_display = ('slug', 'user', 'is_public', 'updated_at')
    list_filter = ('is_public',)
    search_fields = ('slug', 'user__username')


@admin.register(CompanyInquiry)
class CompanyInquiryAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'candidate', 'contact_email', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('company_name', 'contact_email', 'candidate__username')
