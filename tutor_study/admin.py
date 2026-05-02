from django.contrib import admin

from .models import AssignmentSubmission, StudyAssignment, StudyMaterial


class AssignmentSubmissionInline(admin.TabularInline):
    model = AssignmentSubmission
    extra = 0
    raw_id_fields = ('student',)


@admin.register(StudyMaterial)
class StudyMaterialAdmin(admin.ModelAdmin):
    list_display = ('title', 'tutor', 'is_published', 'updated_at')
    list_filter = ('is_published',)
    search_fields = ('title', 'body')
    raw_id_fields = ('tutor',)


@admin.register(StudyAssignment)
class StudyAssignmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'tutor', 'due_at', 'skill', 'updated_at')
    search_fields = ('title', 'instructions')
    raw_id_fields = ('tutor', 'material', 'skill')
    inlines = [AssignmentSubmissionInline]


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'student', 'submitted_at')
    raw_id_fields = ('assignment', 'student')
    search_fields = ('drive_url',)
