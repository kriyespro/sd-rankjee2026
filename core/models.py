from django.db import models
from django.conf import settings

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
