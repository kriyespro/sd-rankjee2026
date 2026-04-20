"""Celery tasks for home tutor marketplace."""

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger('rankjee.hometutor')


@shared_task
def send_demo_reminders():
    """
    ~24h before scheduled_at: email tutor + parent (once per demo).
    Beat should run hourly; window is [T_remind, T_remind + 1h) where T_remind = scheduled_at - 24h.
    """
    from datetime import timedelta

    from .models import DemoRequest

    now = timezone.now()
    qs = DemoRequest.objects.filter(
        status=DemoRequest.Status.ACCEPTED,
        scheduled_at__isnull=False,
        demo_reminder_sent_at__isnull=True,
        scheduled_at__gt=now,
    ).select_related('tutor', 'requester')

    sent = 0
    for demo in qs:
        t_remind = demo.scheduled_at - timedelta(hours=24)
        if not (t_remind <= now < t_remind + timedelta(hours=1)):
            continue

        subject = f'[RankJee] Reminder: demo tomorrow — {demo.tutor.display_name}'
        when = demo.scheduled_at.strftime('%d %b %Y %H:%M')
        base = getattr(settings, 'SITE_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
        body = (
            f'Your demo with {demo.tutor.display_name} is scheduled for {when} (Asia/Kolkata).\n\n'
            f'Parent/student: {demo.requester.get_username()}\n'
            f'Open RankJee: {base}/hometutor/my/requests/ (parent) or {base}/hometutor/my/demos/ (tutor)\n'
        )
        emails = []
        if demo.requester.email:
            emails.append(demo.requester.email)
        tu = demo.tutor.user
        if tu and tu.email:
            emails.append(tu.email)
        for addr in set(emails):
            try:
                send_mail(
                    subject,
                    body,
                    settings.DEFAULT_FROM_EMAIL or 'noreply@localhost',
                    [addr],
                    fail_silently=False,
                )
            except Exception as exc:
                logger.warning('Demo reminder email failed for %s: %s', addr, exc, exc_info=True)
        demo.demo_reminder_sent_at = now
        demo.save(update_fields=['demo_reminder_sent_at', 'updated_at'])
        sent += 1

    return f'demo reminders batch: {sent} sent'
