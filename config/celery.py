
from celery import Celery
from celery.schedules import crontab
import os

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_project.settings')

app = Celery('web_project')

# Load task modules from all registered Django app configs
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Define periodic tasks schedule
app.conf.beat_schedule = {
    # Send session reminders every 5 minutes
    'send-session-reminders': {
        'task': 'apps.booking.tasks.send_session_reminders',
        'schedule': crontab(minute='*/5'),
    },
    # Mark completed sessions every 30 minutes
    'mark-completed-sessions': {
        'task': 'apps.booking.tasks.mark_completed_sessions',
        'schedule': crontab(minute='*/30'),
    },
    # Clean duplicate sessions once a day at midnight
    'clean-duplicate-sessions': {
        'task': 'apps.booking.tasks.clean_duplicate_sessions',
        'schedule': crontab(hour=0, minute=0),
    },
}

# Set timezone for scheduled tasks
app.conf.timezone = 'UTC'