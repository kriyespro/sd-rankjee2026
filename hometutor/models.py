from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify


def _unique_slug_from_display_name(display_name: str, pk: int | None) -> str:
    base = slugify(display_name)[:100] or 'tutor'
    candidate = base
    n = 2
    qs = TutorProfile.objects.all()
    if pk:
        qs = qs.exclude(pk=pk)
    while qs.filter(slug=candidate).exists():
        candidate = f'{base}-{n}'
        n += 1
    return candidate


class TutorProfile(models.Model):
    """Marketplace tutor listing; verification is admin-gated."""

    class TeachingMode(models.TextChoices):
        OFFLINE = 'OFFLINE', 'Offline'
        ONLINE = 'ONLINE', 'Online'
        HYBRID = 'HYBRID', 'Hybrid'

    class VerificationStatus(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        PENDING = 'PENDING', 'Pending review'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    slug = models.SlugField(max_length=120, unique=True, db_index=True, blank=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='tutor_profile',
    )
    display_name = models.CharField(max_length=120)
    profile_image = models.ImageField(
        upload_to='hometutor/profile/%Y/%m/',
        blank=True,
        null=True,
    )
    city = models.CharField(max_length=80, db_index=True)
    area = models.CharField(max_length=120, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    subjects = models.CharField(
        max_length=500,
        help_text='Comma-separated, e.g. Math, Physics',
    )
    teaching_mode = models.CharField(
        max_length=20,
        choices=TeachingMode.choices,
        default=TeachingMode.OFFLINE,
        db_index=True,
    )
    languages = models.CharField(
        max_length=200,
        blank=True,
        help_text='Comma-separated languages, e.g. English, Hindi, Gujarati',
    )
    classes_label = models.CharField(max_length=200, blank=True)
    teaches_from = models.PositiveSmallIntegerField(
        default=6,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    teaches_to = models.PositiveSmallIntegerField(
        default=12,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    fee_label = models.CharField(max_length=80, blank=True)
    bio = models.TextField(blank=True)
    rating_display = models.DecimalField(max_digits=2, decimal_places=1, default=4.5)
    reviews_count = models.PositiveIntegerField(default=0)
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
        db_index=True,
    )
    admin_notes = models.TextField(blank=True)
    is_featured_home = models.BooleanField(
        default=False,
        help_text='Prioritize on the public home page (pilot city).',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_featured_home', '-rating_display', 'display_name']
        indexes = [
            models.Index(fields=['city', 'verification_status']),
        ]

    def __str__(self):
        return f'{self.display_name} ({self.city})'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug_from_display_name(self.display_name, self.pk)
        if self.teaches_from > self.teaches_to:
            self.teaches_from, self.teaches_to = self.teaches_to, self.teaches_from
        if self.pincode:
            geo = PincodeGeo.objects.filter(pincode=self.pincode).first()
            if geo:
                self.latitude = geo.latitude
                self.longitude = geo.longitude
        super().save(*args, **kwargs)

    def covers_class(self, grade: int) -> bool:
        return self.teaches_from <= grade <= self.teaches_to


class DemoRequest(models.Model):
    """Parent/student asks a tutor for a trial class — HT-2."""

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        ACCEPTED = 'ACCEPTED', 'Accepted'
        DECLINED = 'DECLINED', 'Declined'
        CANCELLED = 'CANCELLED', 'Cancelled'

    tutor = models.ForeignKey(
        TutorProfile,
        on_delete=models.CASCADE,
        related_name='demo_requests',
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='demo_requests_sent',
    )
    message = models.TextField(blank=True)
    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        help_text='Optional — helps the tutor reach you.',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Set when the tutor accepts (proposed demo time).',
    )
    decline_reason = models.TextField(blank=True)
    demo_reminder_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Set when ~24h reminder email was sent (idempotent).',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tutor', 'status']),
        ]

    def __str__(self):
        return f'Demo {self.pk} · {self.tutor.display_name} ← {self.requester_id} ({self.status})'


class TutorEngagement(models.Model):
    """Created when a demo is accepted — mutual confirm → ACTIVE (HT-2.1); billing in HT-3."""

    class Status(models.TextChoices):
        PENDING_MUTUAL = 'PENDING_MUTUAL', 'Awaiting both confirmations'
        ACTIVE = 'ACTIVE', 'Confirmed — ready to meet'
        CLOSED = 'CLOSED', 'Closed'

    demo_request = models.OneToOneField(
        DemoRequest,
        on_delete=models.CASCADE,
        related_name='engagement',
    )
    tutor_profile = models.ForeignKey(
        TutorProfile,
        on_delete=models.CASCADE,
        related_name='engagements',
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hometutor_engagements',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING_MUTUAL,
        db_index=True,
    )
    parent_confirmed_at = models.DateTimeField(null=True, blank=True)
    tutor_confirmed_at = models.DateTimeField(null=True, blank=True)
    mutual_confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Engagement {self.pk} · demo {self.demo_request_id} ({self.status})'


class TutorDocument(models.Model):
    """Identity / education proof; staff approves in Django admin (/sd/)."""

    class DocStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    tutor = models.ForeignKey(
        TutorProfile,
        on_delete=models.CASCADE,
        related_name='documents',
    )
    label = models.CharField(max_length=80)
    file = models.FileField(upload_to='hometutor/docs/%Y/%m/')
    status = models.CharField(
        max_length=20,
        choices=DocStatus.choices,
        default=DocStatus.PENDING,
        db_index=True,
    )
    admin_note = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.tutor.display_name} — {self.label} ({self.status})'


class SessionAttendance(models.Model):
    """Tutor marks sessions; parent/student can track attendance history."""

    class AttendanceStatus(models.TextChoices):
        PRESENT = 'PRESENT', 'Present'
        ABSENT = 'ABSENT', 'Absent'
        RESCHEDULED = 'RESCHEDULED', 'Rescheduled'

    engagement = models.ForeignKey(
        TutorEngagement,
        on_delete=models.CASCADE,
        related_name='sessions',
    )
    scheduled_for = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=AttendanceStatus.choices,
        default=AttendanceStatus.PRESENT,
    )
    tutor_note = models.CharField(max_length=255, blank=True)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hometutor_sessions_marked',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-scheduled_for']

    def __str__(self):
        return f'Session {self.engagement_id} {self.scheduled_for:%Y-%m-%d %H:%M} ({self.status})'


class EngagementReview(models.Model):
    """One review per engagement, only from the requester side."""

    engagement = models.OneToOneField(
        TutorEngagement,
        on_delete=models.CASCADE,
        related_name='review',
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hometutor_reviews_written',
    )
    tutor_profile = models.ForeignKey(
        TutorProfile,
        on_delete=models.CASCADE,
        related_name='engagement_reviews',
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Review {self.engagement_id} ({self.rating}/5)'


class EngagementChatMessage(models.Model):
    """Basic in-app chat per engagement; support queue uses flagged messages."""

    engagement = models.ForeignKey(
        TutorEngagement,
        on_delete=models.CASCADE,
        related_name='chat_messages',
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hometutor_chat_messages',
    )
    body = models.TextField(max_length=1000)
    support_flag = models.BooleanField(
        default=False,
        help_text='Sender marked this message for admin support follow-up.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Chat {self.engagement_id} by {self.sender_id}'


class EngagementDispute(models.Model):
    """Dispute raised for an engagement; resolved in admin ops."""

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        IN_REVIEW = 'IN_REVIEW', 'In review'
        RESOLVED = 'RESOLVED', 'Resolved'
        REJECTED = 'REJECTED', 'Rejected'

    engagement = models.ForeignKey(
        TutorEngagement,
        on_delete=models.CASCADE,
        related_name='disputes',
    )
    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hometutor_disputes_raised',
    )
    reason = models.TextField(max_length=2000)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Dispute {self.pk} · engagement {self.engagement_id} ({self.status})'


class PincodeGeo(models.Model):
    """Basic pincode geocoding table for radius search."""

    pincode = models.CharField(max_length=10, unique=True, db_index=True)
    city = models.CharField(max_length=80, blank=True)
    state = models.CharField(max_length=80, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['pincode']

    def __str__(self):
        return f'{self.pincode} ({self.city})'
