from django.contrib import admin
from .models import EarningTask, UserTaskSubmission

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
