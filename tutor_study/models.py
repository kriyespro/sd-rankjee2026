from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

from assessment.models import Skill

drive_link_validator = RegexValidator(
    regex=r'^https?://(drive\.google\.com|docs\.google\.com)/\S+',
    message='Use a Google Drive or Google Docs share link (https://…).',
)


class StudyMaterial(models.Model):
    tutor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='study_materials',
    )
    title = models.CharField(max_length=220)
    body = models.TextField(blank=True, help_text='Notes — plain text, blank lines = paragraphs.')
    attachment = models.FileField(
        upload_to='study/materials/%Y/%m/',
        blank=True,
        null=True,
        help_text='Optional PDF or image.',
    )
    is_published = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title


class StudyAssignment(models.Model):
    tutor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='study_assignments',
    )
    title = models.CharField(max_length=220)
    instructions = models.TextField(blank=True)
    material = models.ForeignKey(
        StudyMaterial,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignments',
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='study_assignments',
        help_text='Optional — links to existing RankJee assessment for this topic.',
    )
    due_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class AssignmentSubmission(models.Model):
    assignment = models.ForeignKey(
        StudyAssignment,
        on_delete=models.CASCADE,
        related_name='submissions',
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assignment_submissions',
    )
    drive_url = models.URLField(max_length=500, validators=[drive_link_validator])
    submitted_at = models.DateTimeField(auto_now_add=True)
    tutor_feedback = models.TextField(blank=True)

    class Meta:
        ordering = ['-submitted_at']
        constraints = [
            models.UniqueConstraint(fields=['assignment', 'student'], name='unique_assignment_student_submission'),
        ]

    def __str__(self):
        return f'{self.student_id} → {self.assignment_id}'
