from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify


class LmsCourse(models.Model):
    """A faculty's own class/course. Students enrol via LmsCourseEnrollment."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lms_courses_owned',
        help_text='Faculty/tutor who owns this course. Empty = platform-wide course (superuser managed).',
    )
    catalog_course = models.ForeignKey(
        'core.Course',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lms_courses',
        help_text='Paid catalog course (/courses/) this batch delivers. Buyers auto-enroll into the default batch for this catalog course.',
    )
    is_default_for_catalog = models.BooleanField(
        default=False,
        help_text='If multiple batches deliver the same catalog course, new buyers auto-enroll into the one marked default.',
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'LMS course'
        verbose_name_plural = 'LMS courses'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:120] or 'course'
            candidate = base
            n = 2
            while LmsCourse.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f'{base}-{n}'
                n += 1
            self.slug = candidate
        super().save(*args, **kwargs)
        if self.owner_id:
            # Owning a course is what makes someone "faculty" — independent of is_staff.
            from django.contrib.auth import get_user_model

            get_user_model().objects.filter(pk=self.owner_id, is_lms_faculty=False).update(
                is_lms_faculty=True
            )
        if self.is_default_for_catalog and self.catalog_course_id:
            LmsCourse.objects.filter(catalog_course_id=self.catalog_course_id).exclude(pk=self.pk).update(
                is_default_for_catalog=False
            )


class LmsCourseEnrollment(models.Model):
    course = models.ForeignKey(LmsCourse, on_delete=models.CASCADE, related_name='enrollments')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lms_course_enrollments',
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-joined_at']
        constraints = [
            models.UniqueConstraint(fields=['course', 'user'], name='unique_lms_course_member'),
        ]

    def __str__(self):
        return f'{self.user_id} ∈ {self.course_id}'


class LmsTopic(models.Model):
    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    description = models.TextField(blank=True)
    course = models.ForeignKey(
        LmsCourse,
        # CASCADE (not SET_NULL): a topic scoped to a course is that course's own curriculum
        # structure — if the course is deleted it should go with it, not silently reappear as a
        # platform-wide topic visible to every student on the platform.
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='topics',
        help_text=(
            'Optional: scope this topic to one course so it appears in that course\'s LMS '
            'sidebar right away, even before any assignment exists under it yet. Empty = '
            'platform-wide topic (only appears once an assignment under it exists).'
        ),
    )
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
    course = models.ForeignKey(
        LmsCourse,
        # CASCADE (not SET_NULL): if a course-scoped assignment's course is deleted, the
        # assignment (and its submissions) must go with it — leaving it as an orphaned
        # "platform-wide" assignment would silently expose it to every student on the platform.
        # Explicitly choosing "platform-wide" on the form (course left empty) is unaffected —
        # this only governs what happens when the referenced course row itself is deleted.
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='assignments',
        help_text='Empty = platform-wide (superuser only). Otherwise scoped to this faculty course.',
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
    study_topic = models.ForeignKey(
        'tutor_study.StudyTopic',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lms_assignments',
        help_text='Optional Study hub topic from /admin/study/ linked to this assignment.',
    )
    skill = models.ForeignKey(
        'assessment.Skill',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lms_assignments',
        help_text='Optional graded test from /assessment/ linked to this assignment — course roster results roll up on the assignment page.',
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        db_index=True,
        help_text='Sequence within its course — controls the order students unlock assignments in (lower first). Ties break by creation order.',
    )
    is_published = models.BooleanField(default=True, db_index=True)
    is_free_preview = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Show this assignment\'s concept_video as the public free preview on the linked catalog course.',
    )
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

    def take_test_url(self) -> str:
        """Deep-link to /assessment/<skill_id>/take/ for this assignment's linked skill test."""
        from django.urls import reverse

        if not self.skill_id:
            return reverse('assessment:index')
        return reverse('assessment:take_test', kwargs={'skill_id': self.skill_id})

    def study_topic_url(self) -> str:
        """Deep-link to /admin/study/topic/<id>/ with return path to this LMS assignment."""
        from django.urls import reverse
        from urllib.parse import urlencode

        if not self.study_topic_id:
            return reverse('dashboard:study')
        base = reverse('dashboard:study_topic', kwargs={'topic_pk': self.study_topic_id})
        return f"{base}?{urlencode({'from_lms': self.pk})}"


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


class LmsAttendance(models.Model):
    """Faculty-marked attendance for a student in a course session."""

    class Status(models.TextChoices):
        PRESENT = 'PRESENT', 'Present'
        ABSENT = 'ABSENT', 'Absent'
        LATE = 'LATE', 'Late'

    course = models.ForeignKey(
        LmsCourse,
        on_delete=models.CASCADE,
        related_name='attendance_records',
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lms_attendance',
    )
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendance_marked',
    )
    date = models.DateField(db_index=True)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ABSENT,
        db_index=True,
    )
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', 'student__username']
        constraints = [
            models.UniqueConstraint(
                fields=['course', 'student', 'date'],
                name='uniq_lms_attendance_per_student_date',
            )
        ]

    def __str__(self):
        return f'{self.student_id} · {self.course_id} · {self.date} — {self.status}'
