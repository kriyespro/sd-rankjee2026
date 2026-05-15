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

    # Career outcomes
    salary_after_min = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True,
        help_text="Min expected salary in LPA after completing this course",
    )
    salary_after_max = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True,
        help_text="Max expected salary in LPA after completing this course",
    )
    job_roles = models.TextField(
        blank=True,
        help_text="Comma-separated job roles after this course. e.g. SEO Analyst, Content Strategist",
    )

    # Structured curriculum — list of {module, title, topics:[...]}
    curriculum = models.JSONField(
        default=list, blank=True,
        help_text='JSON: [{"module":"M1","title":"Foundations","topics":["Topic A","Topic B"]}]',
    )

    # Student testimonials — list of {name, role, city, text, rating}
    testimonials = models.JSONField(
        default=list, blank=True,
        help_text='JSON: [{"name":"Priya","role":"Marketer","city":"Mumbai","text":"...","rating":5}]',
    )

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

    def get_absolute_url(self):
        return f"/courses/{self.slug}/"


class CourseOrder(models.Model):
    """Paid (or free) cart checkout for `Course` catalog — separate from exam Pro `payments.PaymentOrder`."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="course_orders")
    total_inr = models.DecimalField(max_digits=10, decimal_places=2)
    razorpay_order_id = models.CharField(max_length=100, unique=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=200, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"CourseOrder {self.razorpay_order_id} — {self.status}"


class CourseOrderLine(models.Model):
    order = models.ForeignKey(CourseOrder, on_delete=models.CASCADE, related_name="lines")
    course = models.ForeignKey(Course, on_delete=models.PROTECT)
    unit_price_inr = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.course.title} × ₹{self.unit_price_inr}"


class CoursePurchase(models.Model):
    """Lifetime access row after successful checkout (one row per user per course)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="course_purchases")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="purchases")
    order = models.ForeignKey(
        CourseOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchases",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("user", "course"), name="uniq_course_purchase_user_course"),
        ]

    def __str__(self):
        return f"{self.user_id} owns {self.course.slug}"


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
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("18.00"))
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    commission_paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.referrer} → {self.course.title} ({self.status})"


class LegalPage(models.Model):
    """Editable legal/policy pages rendered on public routes and managed from /sd/."""

    class Slug(models.TextChoices):
        TERMS = "terms-and-conditions", "Terms and Conditions"
        PRIVACY = "privacy-policy", "Privacy Policy"
        CANCELLATION = "cancellation-and-refund", "Cancellation and Refund"
        SHIPPING = "shipping-and-exchange", "Shipping and Exchange"
        CONTACT = "contact-us", "Contact Us"

    slug = models.SlugField(max_length=80, unique=True, choices=Slug.choices)
    title = models.CharField(max_length=180)
    content = models.TextField(help_text="Main page content. Use short paragraphs and bullet lines.")
    seo_title = models.CharField(max_length=180, blank=True)
    seo_description = models.CharField(max_length=255, blank=True)
    is_published = models.BooleanField(default=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["slug"]

    def __str__(self):
        return self.title


class TutorLeadRequest(models.Model):
    class RequesterType(models.TextChoices):
        STUDENT = "STUDENT", "Student"
        PARENT = "PARENT", "Parent"

    class Status(models.TextChoices):
        NEW = "NEW", "New"
        CONTACTED = "CONTACTED", "Contacted"
        CLOSED = "CLOSED", "Closed"

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tutor_lead_requests",
    )
    requester_type = models.CharField(max_length=12, choices=RequesterType.choices)
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    city = models.CharField(max_length=80, db_index=True)
    area = models.CharField(max_length=120, blank=True)
    class_grade = models.CharField(max_length=20, blank=True, help_text="e.g. 8, 10, 12")
    board = models.CharField(max_length=40, blank=True, help_text="CBSE / ICSE / GSEB / IB / Other")
    subjects = models.CharField(max_length=250, help_text="Comma-separated subjects")
    teaching_mode = models.CharField(max_length=20, blank=True, help_text="Online / Offline / Hybrid")
    budget_inr = models.PositiveIntegerField(null=True, blank=True)
    start_date_text = models.CharField(max_length=60, blank=True, help_text="When to start")
    schedule_notes = models.CharField(max_length=250, blank=True)
    additional_notes = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.NEW, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} - {self.city} ({self.get_requester_type_display()})"
