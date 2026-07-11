from django.contrib import admin
from django.utils import timezone

from .models import (
    DemoRequest,
    EngagementChatMessage,
    EngagementDispute,
    EngagementReview,
    PincodeGeo,
    SessionAttendance,
    TutorDocument,
    TutorEngagement,
    TutorProfile,
)


class TutorDocumentInline(admin.TabularInline):
    model = TutorDocument
    extra = 0
    readonly_fields = ('uploaded_at', 'reviewed_at')


@admin.register(TutorProfile)
class TutorProfileAdmin(admin.ModelAdmin):
    list_display = (
        'display_name',
        'city',
        'area',
        'fee_label',
        'verification_status',
        'is_featured_home',
        'rating_display',
        'reviews_count',
        'updated_at',
    )
    list_editable = ('fee_label', 'is_featured_home')
    list_filter = ('verification_status', 'city', 'is_featured_home')
    search_fields = ('display_name', 'subjects', 'area', 'slug', 'admin_notes', 'fee_label')
    prepopulated_fields = {'slug': ('display_name',)}
    readonly_fields = ('created_at', 'updated_at')
    inlines = [TutorDocumentInline]
    actions = ('approve_tutors', 'reject_tutors', 'mark_pending')

    @admin.action(description='Approve selected tutor profiles')
    def approve_tutors(self, request, queryset):
        queryset.update(verification_status=TutorProfile.VerificationStatus.APPROVED)

    @admin.action(description='Reject selected tutor profiles')
    def reject_tutors(self, request, queryset):
        queryset.update(verification_status=TutorProfile.VerificationStatus.REJECTED)

    @admin.action(description='Mark selected as pending review')
    def mark_pending(self, request, queryset):
        queryset.update(verification_status=TutorProfile.VerificationStatus.PENDING)


@admin.register(TutorEngagement)
class TutorEngagementAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'demo_request',
        'tutor_profile',
        'student',
        'status',
        'mutual_confirmed_at',
        'created_at',
    )
    list_filter = ('status',)
    raw_id_fields = ('demo_request', 'tutor_profile', 'student')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(DemoRequest)
class DemoRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'tutor', 'requester', 'status', 'scheduled_at', 'created_at')
    list_filter = ('status',)
    search_fields = ('tutor__display_name', 'requester__username', 'requester__email')
    raw_id_fields = ('tutor', 'requester')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(TutorDocument)
class TutorDocumentAdmin(admin.ModelAdmin):
    list_display = ('label', 'tutor', 'status', 'uploaded_at', 'reviewed_at')
    list_filter = ('status',)
    search_fields = ('label', 'tutor__display_name')
    readonly_fields = ('uploaded_at',)
    actions = ('approve_docs', 'reject_docs')

    @admin.action(description='Approve selected documents')
    def approve_docs(self, request, queryset):
        queryset.update(
            status=TutorDocument.DocStatus.APPROVED,
            reviewed_at=timezone.now(),
        )

    @admin.action(description='Reject selected documents')
    def reject_docs(self, request, queryset):
        queryset.update(
            status=TutorDocument.DocStatus.REJECTED,
            reviewed_at=timezone.now(),
        )


@admin.register(SessionAttendance)
class SessionAttendanceAdmin(admin.ModelAdmin):
    list_display = ('engagement', 'scheduled_for', 'status', 'marked_by', 'created_at')
    list_filter = ('status',)
    raw_id_fields = ('engagement', 'marked_by')
    readonly_fields = ('created_at',)


@admin.register(EngagementReview)
class EngagementReviewAdmin(admin.ModelAdmin):
    list_display = ('engagement', 'tutor_profile', 'reviewer', 'rating', 'created_at')
    list_filter = ('rating',)
    raw_id_fields = ('engagement', 'tutor_profile', 'reviewer')
    readonly_fields = ('created_at',)


@admin.register(EngagementChatMessage)
class EngagementChatMessageAdmin(admin.ModelAdmin):
    list_display = ('engagement', 'sender', 'support_flag', 'created_at')
    list_filter = ('support_flag',)
    search_fields = ('body', 'sender__username', 'engagement__id')
    raw_id_fields = ('engagement', 'sender')
    readonly_fields = ('created_at',)


@admin.register(EngagementDispute)
class EngagementDisputeAdmin(admin.ModelAdmin):
    list_display = ('engagement', 'raised_by', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('reason', 'admin_note')
    raw_id_fields = ('engagement', 'raised_by')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PincodeGeo)
class PincodeGeoAdmin(admin.ModelAdmin):
    list_display = ('pincode', 'city', 'state', 'latitude', 'longitude', 'is_active')
    list_filter = ('is_active', 'state')
    search_fields = ('pincode', 'city', 'state')
