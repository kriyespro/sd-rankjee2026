"""
Signal: when an admin manually approves a UserTaskSubmission via Django admin,
trigger the gamification on_task_approved helper.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import UserTaskSubmission
from users.gamification import on_task_approved


@receiver(post_save, sender=UserTaskSubmission)
def submission_approved_signal(sender, instance, created, **kwargs):
    if not created and instance.status == 'APPROVED':
        # Idempotent: on_task_approved skips if EARN_TASK already logged for this task
        on_task_approved(instance.user, instance.task)
