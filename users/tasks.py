from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
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
                if user.streak_days > 0:
                    user.streak_days = 0
                    user.save(update_fields=['streak_days'])
                    reset_count += 1
                    # Dispatch reminder email
                    send_reminder_email.delay(user.id)
                
    return f"Reset streaks for {reset_count} users."

@shared_task
def send_reminder_email(user_id):
    """
    Task to send a reminder email to a user who broke their streak.
    """
    try:
        user = CustomUser.objects.get(pk=user_id)
        if not user.email:
            return "User has no email."
            
        subject = "Don't lose your progress! 🔥"
        message = f"Hi {user.username},\n\nWe noticed you missed a day on SkillLoop and your streak has reset. Consistency is key to unlocking rewards and earning more.\n\nJump back in today to start a new streak and claim your daily reward!\n\nBest,\nThe SkillLoop Team"
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True,
        )
        return f"Reminder sent to user {user_id}"
    except CustomUser.DoesNotExist:
        return "User not found."
