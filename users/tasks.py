from celery import shared_task
from django.utils import timezone
from .models import CustomUser

@shared_task
def check_and_reset_streaks():
    """
    Background task to check all users and reset streak if they missed a day.
    Runs daily.
    """
    today = timezone.now().date()
    users = CustomUser.objects.filter(is_active=True)
    reset_count = 0
    
    for user in users:
        if user.last_active_date:
            days_inactive = (today - user.last_active_date).days
            if days_inactive > 1:
                user.streak_days = 0
                user.save(update_fields=['streak_days'])
                reset_count += 1
                
    return f"Reset streaks for {reset_count} users."

@shared_task
def send_reminder_email(user_id):
    """
    Example task to send a reminder email.
    """
    # Placeholder for actual email sending logic
    return f"Reminder sent to user {user_id}"
