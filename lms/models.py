from django.conf import settings
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


class LmsTopic(models.Model):
    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['title']
        verbose_name = 'LMS topic'
        verbose_name_plural = 'LMS topics'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:150] or 'topic'
            candidate = base
            n = 2
            while LmsTopic.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f'{base}-{n}'
                n += 1
            self.slug = candidate
        super().save(*args, **kwargs)


class LmsAssignment(models.Model):
    topic = models.ForeignKey(
        LmsTopic,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignments',
    )
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
    concept_video = models.ForeignKey(
        'learning.ConceptVideo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lms_assignments',
        help_text='Optional lecture recording from /learning/ linked to this assignment.',
    )
    is_published = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['topic__title', '-created_at']

    def __str__(self):
        return self.title

    def learning_lecture_url(self) -> str:
        """Deep-link to /learning/ scrolled to this lecture video."""
        from django.urls import reverse
        from urllib.parse import urlencode

        if not self.concept_video_id:
            return reverse('learning:index')
        video = self.concept_video
        params = {'video_id': video.pk}
        if video.skill_id:
            params['skill'] = video.skill_id
        if video.concept_tag:
            params['concept'] = video.concept_tag
        return f"{reverse('learning:index')}?{urlencode(params)}"


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
        # URL rows validated in LmsSubmissionForm; legacy fields kept for old rows.
        pass

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


class LmsSubmissionUrl(models.Model):
    class Kind(models.TextChoices):
        DRIVE = 'DRIVE', 'Google Drive'
        WEBSITE = 'WEBSITE', 'Website'

    submission = models.ForeignKey(
        LmsSubmission,
        on_delete=models.CASCADE,
        related_name='urls',
    )
    url = models.URLField(max_length=500)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.DRIVE)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f'{self.get_kind_display()}: {self.url[:60]}'
