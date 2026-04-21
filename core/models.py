from django.db import models
from django.conf import settings
from django.utils.text import slugify
from decimal import Decimal

class EarningTask(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    reward_amount = models.IntegerField(default=50, help_text="In INR")
    required_skill = models.ForeignKey('assessment.Skill', on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    auto_approve_domain = models.CharField(
        max_length=100, blank=True,
        help_text="If proof URL contains this domain, auto-approve the submission (e.g. youtube.com)"
    )

    def __str__(self):
        return f"{self.title} (₹{self.reward_amount})"

class UserTaskSubmission(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    task = models.ForeignKey(EarningTask, on_delete=models.CASCADE)
    proof_url = models.URLField(blank=True, help_text="Link to proof")
    proof_text = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.task.title} [{self.status}]"


class Course(models.Model):
    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    short_description = models.CharField(max_length=260, blank=True)
    description = models.TextField(blank=True)
    price_inr = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    duration_weeks = models.PositiveIntegerField(default=4)
    level = models.CharField(max_length=40, blank=True, help_text="Beginner / Intermediate / Advanced")
    thumbnail_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_featured", "title"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:180] or "course"
            candidate = base
            i = 1
            while Course.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                i += 1
                candidate = f"{base}-{i}"[:200]
            self.slug = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} (₹{self.price_inr})"


class CourseReferral(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESS = "SUCCESS", "Success"
        REJECTED = "REJECTED", "Rejected"

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="referrals")
    referrer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="course_referrals")
    lead_email = models.EmailField()
    lead_name = models.CharField(max_length=120, blank=True)
    lead_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="course_referral_leads",
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    sale_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("30.00"))
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    commission_paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.referrer} → {self.course.title} ({self.status})"
