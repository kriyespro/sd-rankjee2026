from django.contrib import admin
from django.db.models import Q

from .models import (
    LmsAssignment,
    LmsComment,
    LmsCourse,
    LmsCourseEnrollment,
    LmsReaction,
    LmsSubmission,
    LmsTopic,
)


def _owned_assignment_ids(user):
    """Assignment PKs visible to a non-superuser staff (faculty): own courses + platform-wide."""
    return LmsAssignment.objects.filter(
        Q(course__owner_id=user.id) | Q(course__isnull=True)
    ).values_list('pk', flat=True)


class LmsCourseEnrollmentInline(admin.TabularInline):
    model = LmsCourseEnrollment
    extra = 1
    raw_id_fields = ('user',)


@admin.register(LmsCourse)
class LmsCourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'catalog_course', 'is_default_for_catalog', 'slug', 'is_active', 'created_at')
    list_filter = ('is_active', 'is_default_for_catalog')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'slug', 'owner__username', 'catalog_course__title')
    raw_id_fields = ('owner', 'catalog_course')
    inlines = [LmsCourseEnrollmentInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(owner_id=request.user.id)

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.owner = request.user
        super().save_model(request, obj, form, change)


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
        'study_topic',
        'skill',
        'course',
        'due_at',
        'is_published',
        'created_by',
        'created_at',
    )
    list_filter = ('topic', 'is_published', 'course')
    search_fields = ('title', 'instructions')
    raw_id_fields = ('created_by', 'topic', 'course', 'concept_video', 'study_topic', 'skill')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(Q(course__owner_id=request.user.id) | Q(course__isnull=True))

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'course' and not request.user.is_superuser:
            kwargs['queryset'] = LmsCourse.objects.filter(owner_id=request.user.id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


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

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(assignment_id__in=_owned_assignment_ids(request.user))


@admin.register(LmsReaction)
class LmsReactionAdmin(admin.ModelAdmin):
    list_display = ('submission', 'user', 'value', 'created_at')
    list_filter = ('value',)
    raw_id_fields = ('submission', 'user')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(submission__assignment_id__in=_owned_assignment_ids(request.user))


@admin.register(LmsComment)
class LmsCommentAdmin(admin.ModelAdmin):
    list_display = ('submission', 'user', 'created_at')
    search_fields = ('body', 'user__username')
    raw_id_fields = ('submission', 'user')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(submission__assignment_id__in=_owned_assignment_ids(request.user))
