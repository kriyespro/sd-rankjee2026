from celery import shared_task
from django.utils import timezone
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template
from django.utils.html import strip_tags
from .models import CustomUser


def _site_base_url():
    return getattr(settings, "SITE_BASE_URL", "").rstrip("/") or "http://127.0.0.1:8000"


def _send_templated_email(*, to_email: str, subject: str, template_name: str, context: dict):
    html = get_template(template_name).render(context)
    text = strip_tags(html)
    msg = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [to_email])
    msg.attach_alternative(html, "text/html")
    msg.send(fail_silently=True)

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
            
        subject = "Don't lose your progress!"
        _send_templated_email(
            to_email=user.email,
            subject=subject,
            template_name="email/streak_break.jinja",
            context={
                "user": user,
                "dashboard_url": f"{_site_base_url()}/admin/",
            },
        )
        return f"Reminder sent to user {user_id}"
    except CustomUser.DoesNotExist:
        return "User not found."


@shared_task
def send_welcome_email(user_id):
    try:
        user = CustomUser.objects.get(pk=user_id)
        if not user.email:
            return "User has no email."
        _send_templated_email(
            to_email=user.email,
            subject="Welcome to RankJee",
            template_name="email/welcome.jinja",
            context={
                "user": user,
                "dashboard_url": f"{_site_base_url()}/admin/",
            },
        )
        return f"Welcome sent to user {user_id}"
    except CustomUser.DoesNotExist:
        return "User not found."


@shared_task
def send_withdrawal_status_email(withdrawal_id):
    from .models import WithdrawalRequest

    try:
        w = WithdrawalRequest.objects.select_related("user").get(pk=withdrawal_id)
    except WithdrawalRequest.DoesNotExist:
        return "Withdrawal not found."
    if not w.user.email:
        return "User has no email."
    _send_templated_email(
        to_email=w.user.email,
        subject="Withdrawal status update",
        template_name="email/withdrawal_update.jinja",
        context={
            "user": w.user,
            "amount": w.amount,
            "upi_id": w.upi_id,
            "status": w.get_status_display(),
            "admin_note": w.admin_note,
            "earnings_url": f"{_site_base_url()}/earnings/",
        },
    )
    return f"Withdrawal update sent for {withdrawal_id}"
