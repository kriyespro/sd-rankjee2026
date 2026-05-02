from django.contrib import admin

from .models import AssignmentSubmission, StudyAssignment, StudyMaterial, StudyTopic


class AssignmentSubmissionInline(admin.TabularInline):
    model = AssignmentSubmission
    extra = 0
    raw_id_fields = ('student',)


@admin.register(StudyTopic)
class StudyTopicAdmin(admin.ModelAdmin):
    list_display = ('title', 'tutor', 'parent', 'sort_order')
    list_filter = ('tutor',)
    search_fields = ('title', 'slug')
    raw_id_fields = ('tutor', 'parent')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(StudyMaterial)
class StudyMaterialAdmin(admin.ModelAdmin):
    list_display = ('title', 'tutor', 'study_topic', 'is_published', 'updated_at')
    list_filter = ('is_published',)
    search_fields = ('title', 'body')
    raw_id_fields = ('tutor', 'study_topic')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == 'tutor':
            formfield.help_text = (
                'Published notes whose tutor is a staff or superuser appear for '
                'every logged-in student on /study/ (no tutor engagement required).'
            )
        return formfield


@admin.register(StudyAssignment)
class StudyAssignmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'tutor', 'study_topic', 'due_at', 'skill', 'updated_at')
    search_fields = ('title', 'instructions')
    raw_id_fields = ('tutor', 'material', 'skill', 'study_topic')
    inlines = [AssignmentSubmissionInline]


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'student', 'submitted_at')
    raw_id_fields = ('assignment', 'student')
    search_fields = ('drive_url',)
