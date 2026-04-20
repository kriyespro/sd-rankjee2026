"""Recurring fee reminder tasks for home tutor marketplace."""

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.utils import timezone

from .models import MarketplaceOrder

logger = logging.getLogger('rankjee.hometutor_payments')


@shared_task
def send_recurring_fee_reminders():
    """
    Remind parent/student around monthly renewal window.
    Uses cache key per order+month to avoid duplicate reminders.
    """
    now = timezone.now()
    window_start = now - timedelta(days=32)
    window_end = now - timedelta(days=27)
    qs = MarketplaceOrder.objects.filter(
        status=MarketplaceOrder.Status.SUCCESS,
        paid_at__gte=window_start,
        paid_at__lte=window_end,
    ).select_related('engagement', 'engagement__tutor_profile', 'payer')

    sent = 0
    month_key = now.strftime('%Y-%m')
    base = getattr(settings, 'SITE_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
    from_email = settings.DEFAULT_FROM_EMAIL or 'noreply@localhost'
    for order in qs:
        ck = f'hometutor:renew-reminder:{order.pk}:{month_key}'
        if cache.get(ck):
            continue
        tutor_name = order.engagement.tutor_profile.display_name
        pay_link = f'{base}/hometutor/payments/pay/{order.engagement_id}/'
        subject = f'[RankJee] Monthly fee reminder for {tutor_name}'
        body = (
            f'Your previous marketplace fee for {tutor_name} was paid on {order.paid_at:%d %b %Y}.\n\n'
            f'If classes are continuing, please renew this month to keep billing records updated.\n'
            f'Renew link: {pay_link}\n'
        )
        recipients = [order.payer.email] if order.payer.email else []
        if not recipients:
            continue
        try:
            send_mail(subject, body, from_email, recipients, fail_silently=False)
            cache.set(ck, 1, 60 * 60 * 24 * 45)
            sent += 1
        except Exception as exc:
            logger.warning('Recurring fee reminder failed for order=%s: %s', order.pk, exc)
    return f'recurring reminders sent: {sent}'
