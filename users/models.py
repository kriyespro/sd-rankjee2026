import uuid
from django.contrib.auth.models import AbstractUser
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
    state = models.CharField(max_length=2, choices=INDIAN_STATES, blank=True, null=True)
    streak_days = models.IntegerField(default=0)
    last_active_date = models.DateField(null=True, blank=True)
    xp_points = models.IntegerField(default=0)
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # ₹ earnings
    trial_tests_left = models.IntegerField(default=3)
    referral_code = models.CharField(max_length=10, unique=True, default=_gen_referral_code)
    referred_by = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='referrals'
    )

    def add_xp(self, points):
        self.xp_points += points
        self.save(update_fields=['xp_points'])

    def add_wallet(self, amount, transaction_type='OTHER', reference_id=None):
        from decimal import Decimal
        amount_dec = Decimal(str(amount))
        self.wallet_balance += amount_dec
        self.save(update_fields=['wallet_balance'])
        
        # Log Transaction
        WalletTransaction.objects.create(
            user=self,
            amount=amount_dec,
            transaction_type=transaction_type,
            reference_id=reference_id
        )
    @property
    def is_premium(self):
        """Check if user has an active, non-expired subscription."""
        try:
            return self.subscription.is_active and not self.subscription.is_expired
        except:
            return False


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
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    admin_note = models.TextField(blank=True, null=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        return f"{self.user.username} - ₹{self.amount} ({self.status})"

