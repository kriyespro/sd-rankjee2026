import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rankjee.settings')

app = Celery('rankjee')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

from celery.schedules import crontab

app.conf.beat_schedule = {
    'check-streaks-daily': {
        'task': 'users.tasks.check_and_reset_streaks',
        'schedule': crontab(hour=0, minute=5),
    },
    'hometutor-demo-reminders-hourly': {
        'task': 'hometutor.tasks.send_demo_reminders',
        'schedule': crontab(minute=12),
    },
    'hometutor-recurring-fee-reminders-daily': {
        'task': 'hometutor_payments.tasks.send_recurring_fee_reminders',
        'schedule': crontab(hour=10, minute=0),
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
