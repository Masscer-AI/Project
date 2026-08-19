from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.settings")

app = Celery("api")

app.config_from_object("django.conf:settings", namespace="CELERY")

from django.conf import settings as django_settings

# Celery also reads CELERY_RESULT_BACKEND from the process env (.env is
# redis://localhost:6379/0). That overrides Django's django-db backend and
# makes .delay() pubsub against localhost inside Docker.
app.conf.broker_url = django_settings.CELERY_BROKER_URL
app.conf.result_backend = django_settings.CELERY_RESULT_BACKEND

app.autodiscover_tasks()

import api.ai_layers.platform_assistant_task  # noqa: F401

app.conf.beat_schedule = {
    'check-pending-conversations': {
        'task': 'api.messaging.tasks.check_pending_conversations',
        'schedule': 180.0,
    },
    'run-due-scheduled-conversation-tasks': {
        'task': 'api.messaging.tasks.run_due_scheduled_conversation_tasks',
        'schedule': 60.0,
    },
    'expire-subscriptions-past-end-date': {
        'task': 'api.payments.tasks.expire_subscriptions_past_end_date',
        'schedule': crontab(minute=12),
    },
    'purge-expired-data': {
        'task': 'api.data_governance.tasks.purge_expired_data',
        'schedule': crontab(hour=3, minute=0),
    },
    'expire-stale-data-exports': {
        'task': 'api.data_governance.tasks.expire_stale_data_exports',
        'schedule': crontab(hour=4, minute=0),
    },
}

import api.celery_signals
