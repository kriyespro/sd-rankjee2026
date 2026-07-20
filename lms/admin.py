from django.contrib import admin

from .models import (
    LmsAssignment,
    LmsBatch,
    LmsBatchMembership,
    LmsComment,
    LmsReaction,
    LmsSubmission,
    LmsTopic,
)


class LmsBatchMembershipInline(admin.TabularInline):
    model = LmsBatchMembership
    extra = 1
    raw_id_fields = ('user',)


@admin.register(LmsBatch)
class LmsBatchAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'created_at')
    list_filter = ('is_active',)
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'slug')
    inlines = [LmsBatchMembershipInline]


@admin.register(LmsTopic)
class LmsTopicAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'created_at')
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ('title', 'description')


@admin.register(LmsAssignment)
class LmsAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'topic',
        'concept_video',
        'batch',
        'due_at',
        'is_published',
        'created_by',
        'created_at',
    )
    list_filter = ('topic', 'is_published', 'batch')
    search_fields = ('title', 'instructions')
    raw_id_fields = ('created_by', 'topic', 'batch', 'concept_video')


@admin.register(LmsSubmission)
class LmsSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'assignment',
        'student',
        'status',
        'marks',
        'is_pinned',
        'updated_at',
    )
    list_filter = ('status', 'is_pinned')
    search_fields = ('student__username', 'assignment__title', 'caption')
    raw_id_fields = ('assignment', 'student')


@admin.register(LmsReaction)
class LmsReactionAdmin(admin.ModelAdmin):
    list_display = ('submission', 'user', 'value', 'created_at')
    list_filter = ('value',)
    raw_id_fields = ('submission', 'user')


@admin.register(LmsComment)
class LmsCommentAdmin(admin.ModelAdmin):
    list_display = ('submission', 'user', 'created_at')
    search_fields = ('body', 'user__username')
    raw_id_fields = ('submission', 'user')
