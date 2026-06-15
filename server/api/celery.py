from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.settings")

app = Celery("api")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# Explicitly import api.tasks to register tasks in the api module
import api.tasks
import api.ai_layers.platform_assistant_task  # noqa: F401

# Configure periodic tasks
app.conf.beat_schedule = {
    'check-pending-conversations': {
        'task': 'api.messaging.tasks.check_pending_conversations',
        'schedule': 180.0,  # Run every 3 minutes (180 seconds)
    },
    'expire-subscriptions-past-end-date': {
        'task': 'api.payments.tasks.expire_subscriptions_past_end_date',
        'schedule': crontab(minute=12),  # hourly
    },
    'purge-expired-data': {
        'task': 'api.data_governance.tasks.purge_expired_data',
        'schedule': crontab(hour=3, minute=0),  # daily at 03:00 UTC
    },
    'expire-stale-data-exports': {
        'task': 'api.data_governance.tasks.expire_stale_data_exports',
        'schedule': crontab(hour=4, minute=0),  # daily at 04:00 UTC
    },
}

import api.celery_signals
