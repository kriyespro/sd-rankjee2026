from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify


class LmsBatch(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'LMS batch'
        verbose_name_plural = 'LMS batches'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:120] or 'batch'
            candidate = base
            n = 2
            while LmsBatch.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f'{base}-{n}'
                n += 1
            self.slug = candidate
        super().save(*args, **kwargs)


class LmsBatchMembership(models.Model):
    batch = models.ForeignKey(LmsBatch, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lms_batch_memberships',
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-joined_at']
        constraints = [
            models.UniqueConstraint(fields=['batch', 'user'], name='unique_lms_batch_member'),
        ]

    def __str__(self):
        return f'{self.user_id} ∈ {self.batch_id}'


class LmsAssignment(models.Model):
    batch = models.ForeignKey(
        LmsBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignments',
        help_text='Empty = visible to all STUDENT users.',
    )
    title = models.CharField(max_length=220)
    instructions = models.TextField(blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='lms_assignments_created',
    )
    is_published = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class LmsSubmission(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = 'SUBMITTED', 'Submitted'
        APPROVED = 'APPROVED', 'Approved'
        CHANGES_REQUESTED = 'CHANGES_REQUESTED', 'Changes requested'

    assignment = models.ForeignKey(
        LmsAssignment,
        on_delete=models.CASCADE,
        related_name='submissions',
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lms_submissions',
    )
    caption = models.TextField(blank=True)
    image = models.ImageField(upload_to='lms/submissions/%Y/%m/', blank=True, null=True)
    file = models.FileField(upload_to='lms/submissions/%Y/%m/', blank=True, null=True)
    video_url = models.URLField(max_length=500, blank=True)
    website_url = models.URLField(max_length=500, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SUBMITTED,
        db_index=True,
    )
    marks = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    remark = models.TextField(blank=True)
    is_pinned = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-updated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['assignment', 'student'],
                name='unique_lms_assignment_student',
            ),
        ]

    def __str__(self):
        return f'{self.student_id} → {self.assignment_id}'

    def clean(self):
        has_media = bool(
            self.image
            or self.file
            or (self.video_url or '').strip()
            or (self.website_url or '').strip()
        )
        if not has_media:
            raise ValidationError('Add an image, PDF, video link, or website URL.')

    @property
    def star_rating(self) -> int:
        if self.marks is None:
            return 0
        return max(1, min(5, round(self.marks / 20)))


class LmsReaction(models.Model):
    class Value(models.TextChoices):
        LIKE = 'LIKE', 'Like'
        DISLIKE = 'DISLIKE', 'Dislike'

    submission = models.ForeignKey(
        LmsSubmission,
        on_delete=models.CASCADE,
        related_name='reactions',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lms_reactions',
    )
    value = models.CharField(max_length=10, choices=Value.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['submission', 'user'],
                name='unique_lms_reaction_user',
            ),
        ]

    def __str__(self):
        return f'{self.user_id} {self.value} {self.submission_id}'


class LmsComment(models.Model):
    submission = models.ForeignKey(
        LmsSubmission,
        on_delete=models.CASCADE,
        related_name='comments',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lms_comments',
    )
    body = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Comment {self.pk} on {self.submission_id}'
