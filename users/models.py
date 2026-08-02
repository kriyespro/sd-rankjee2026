import uuid
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ObjectDoesNotExist
from django.db import models


def _gen_referral_code():
    return uuid.uuid4().hex[:8].upper()

INDIAN_STATES = [
    ('AP', 'Andhra Pradesh'), ('AR', 'Arunachal Pradesh'), ('AS', 'Assam'),
    ('BR', 'Bihar'), ('CT', 'Chhattisgarh'), ('GA', 'Goa'),
    ('GJ', 'Gujarat'), ('HR', 'Haryana'), ('HP', 'Himachal Pradesh'),
    ('JH', 'Jharkhand'), ('KA', 'Karnataka'), ('KL', 'Kerala'),
    ('MP', 'Madhya Pradesh'), ('MH', 'Maharashtra'), ('MN', 'Manipur'),
    ('ML', 'Meghalaya'), ('MZ', 'Mizoram'), ('NL', 'Nagaland'),
    ('OR', 'Odisha'), ('PB', 'Punjab'), ('RJ', 'Rajasthan'),
    ('SK', 'Sikkim'), ('TN', 'Tamil Nadu'), ('TG', 'Telangana'),
    ('TR', 'Tripura'), ('UP', 'Uttar Pradesh'), ('UT', 'Uttarakhand'),
    ('WB', 'West Bengal'), ('CH', 'Chandigarh'), ('DL', 'Delhi'),
    ('JK', 'Jammu & Kashmir'), ('LA', 'Ladakh')
]

class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = 'STUDENT', 'Student'
        PARENT = 'PARENT', 'Parent'
        TUTOR = 'TUTOR', 'Tutor'
        VIP_USER = 'VIP_USER', 'VIP user'
        CITY_ADMIN = 'CITY_ADMIN', 'City admin'
        GLOBAL_ADMIN = 'GLOBAL_ADMIN', 'Global admin'
        # Reporting/label only — NOT the LMS permission gate (that's is_staff/is_superuser).
        # Never added to the public signup role picker.
        FACULTY = 'FACULTY', 'Faculty'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
        db_index=True,
    )
    state = models.CharField(max_length=2, choices=INDIAN_STATES, blank=True, null=True)
    streak_days = models.IntegerField(default=0)
    last_active_date = models.DateField(null=True, blank=True)
    last_ad_claim_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Server-side last ad reward claim (anti-abuse).",
    )
    xp_points = models.IntegerField(default=0)
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # ₹ earnings
    trial_tests_left = models.IntegerField(default=3)
    trial_tests_used = models.IntegerField(
        default=0,
        help_text="Lifetime trials consumed (prevents cookie/session reset abuse).",
    )
    referral_code = models.CharField(max_length=10, unique=True, default=_gen_referral_code)
    referred_by = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='referrals'
    )
    is_vip_testing_user = models.BooleanField(
        default=False,
        db_index=True,
        help_text="If set, user always has exam Pro access (feedback / QA). Manage from /sd/.",
    )
    show_server_buy_button = models.BooleanField(
        default=False,
        db_index=True,
        help_text="If set, student sees “Server buy now” on dashboard and can open server checkout.",
    )
    signup_pro_trial_applied_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Set when the one-time signup Pro trial was applied (payments module).",
    )
    onboarding_completed = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Role/profile onboarding completion gate for login redirects.",
    )
    is_lms_faculty = models.BooleanField(
        default=False,
        db_index=True,
        help_text=(
            "Grants LMS batch-teaching access (own courses/students only), independent of "
            "is_staff (which only controls /sd/ Django admin access). Auto-set True the first "
            "time this user is assigned ownership of an LmsCourse."
        ),
    )
    # Contact info — mandatory at signup/onboarding (form-level) for every public role.
    # blank=True at the DB level only so pre-existing accounts don't break; forms enforce it.
    phone = models.CharField(
        max_length=15,
        blank=True,
        default='',
        help_text="Mobile number (Indian 10-digit, optional +91).",
    )
    city = models.CharField(
        max_length=60,
        blank=True,
        default='',
        help_text="City the user lives/teaches in.",
    )

    def add_xp(self, points):
        self.xp_points += points
        self.save(update_fields=['xp_points'])

    def add_wallet(self, amount, transaction_type='OTHER', reference_id=None):
        import logging
        from decimal import Decimal

        from django.db import transaction as _transaction
        from django.db.models import F

        amount_dec = Decimal(str(amount))
        # Atomic F()-expression update under a row lock — avoids lost updates when two
        # requests (e.g. concurrent webhook retries) credit/debit the same wallet at once.
        with _transaction.atomic():
            type(self).objects.filter(pk=self.pk).select_for_update().update(
                wallet_balance=F('wallet_balance') + amount_dec
            )
            WalletTransaction.objects.create(
                user=self,
                amount=amount_dec,
                transaction_type=transaction_type,
                reference_id=reference_id,
            )
        self.refresh_from_db(fields=['wallet_balance'])
        logging.getLogger('rankjee.wallet').info(
            'wallet user=%s amount=%s type=%s ref=%s balance=%s',
            self.username,
            amount_dec,
            transaction_type,
            reference_id,
            self.wallet_balance,
        )
    @property
    def is_premium(self):
        """Exam Pro (payments subscription), VIP tester flag, or active paid/complimentary sub."""
        from django.conf import settings

        # Temporary free access for all until EXAM_PAYWALL_ENABLED is turned back on.
        if not getattr(settings, 'EXAM_PAYWALL_ENABLED', True):
            return True
        cached = getattr(self, "_cached_is_premium", None)
        if cached is not None:
            return cached
        if getattr(self, 'role', None) == self.Role.VIP_USER:
            return True
        if self.is_vip_testing_user:
            return True
        try:
            sub = self.subscription
        except ObjectDoesNotExist:
            return False
        return sub.is_active and not sub.is_expired


class ParentStudentLink(models.Model):
    """Read-only visibility link: once a Student approves, the linked Parent can see that
    student's progress (exam results, LMS courses) — see fix-rankjee.md Phase 2.

    Pending until the student approves, so a Parent account can't snoop on an arbitrary
    student just by knowing their username/email.
    """

    parent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='parent_links',
        help_text='The Parent account requesting visibility.',
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='student_links',
        help_text='The Student account being viewed.',
    )
    relationship_label = models.CharField(
        max_length=40, blank=True, help_text='e.g. Mother, Father, Guardian'
    )
    is_verified = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Student must approve before the parent gets any read-only access.',
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-requested_at']
        constraints = [
            models.UniqueConstraint(fields=['parent', 'student'], name='unique_parent_student_link'),
        ]

    def __str__(self):
        status = 'verified' if self.is_verified else 'pending'
        return f'{self.parent_id} -> {self.student_id} ({status})'


class Badge(models.Model):
    BADGE_TYPES = [
        ('FIRST_TEST', '🎯 First Test'),
        ('FIRST_PASS', '🏆 First Pass'),
        ('FIRST_EARN', '💰 First Earn'),
        ('REFERRAL', '🤝 Referral Star'),
        ('STREAK_7', '🔥 7-Day Streak'),
        ('STREAK_30', '⚡ 30-Day Streak'),
    ]
    badge_type = models.CharField(max_length=20, choices=BADGE_TYPES, unique=True)
    title = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=10, default='🏅')

    def __str__(self):
        return self.title


class UserBadge(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE)
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'badge')

    def __str__(self):
        return f"{self.user.username} – {self.badge.title}"


class Notification(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=300)
    link = models.CharField(max_length=200, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.user.username}] {self.message[:50]}"


class WalletTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('EARN_TASK', 'Task Earning'),
        ('EARN_REFERRAL', 'Referral Bonus'),
        ('EARN_DAILY', 'Daily Login Bonus'),
        ('EARN_JACKPOT', 'Jackpot Reward'),
        ('CREDIT_SIGNUP', 'Signup Credit'),
        ('CREDIT_ADMIN', 'Admin Credit'),
        ('DEDUCT_TEST', 'Test Deduction'),
        ('DEDUCT_WITHDRAW', 'Withdrawal'),
        ('OTHER', 'Other'),
    ]
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='wallet_transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # negative for deductions
    transaction_type = models.CharField(max_length=50, choices=TRANSACTION_TYPES, default='OTHER')
    reference_id = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.get_transaction_type_display()} - ₹{self.amount}"


class WithdrawalRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSED', 'Processed'),
        ('REJECTED', 'Rejected'),
    ]
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='withdrawals')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    upi_id = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    admin_note = models.TextField(blank=True, null=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        return f"{self.user.username} - ₹{self.amount} ({self.status})"


class PublicProfile(models.Model):
    """Opt-in public page for employers (FEATURE-15)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='public_profile',
    )
    is_public = models.BooleanField(default=False)
    slug = models.SlugField(max_length=80, unique=True, db_index=True)
    headline = models.CharField(max_length=200, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['slug']

    def __str__(self):
        return f"{self.slug} ({self.user.username})"


class CompanyInquiry(models.Model):
    STATUS_CHOICES = [
        ('NEW', 'New'),
        ('READ', 'Read'),
    ]
    candidate = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='company_inquiries',
    )
    company_name = models.CharField(max_length=200)
    contact_email = models.EmailField()
    message = models.TextField(max_length=2000)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='NEW')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Company inquiries'

    def __str__(self):
        return f"{self.company_name} → {self.candidate.username}"

