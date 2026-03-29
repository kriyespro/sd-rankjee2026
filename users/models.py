import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


def _gen_referral_code():
    return uuid.uuid4().hex[:8].upper()


class CustomUser(AbstractUser):
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

    def add_wallet(self, amount):
        from decimal import Decimal
        self.wallet_balance += Decimal(str(amount))
        self.save(update_fields=['wallet_balance'])


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

