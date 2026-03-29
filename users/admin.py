from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Badge, UserBadge, Notification


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'streak_days', 'xp_points', 'wallet_balance', 'referral_code')
    readonly_fields = ('referral_code',)
    fieldsets = UserAdmin.fieldsets + (
        ('SkillLoop', {'fields': ('streak_days', 'xp_points', 'wallet_balance', 'last_active_date', 'referral_code', 'referred_by')}),
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
