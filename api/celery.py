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

# Configure periodic tasks
app.conf.beat_schedule = {
    'check-pending-conversations': {
        'task': 'api.messaging.tasks.check_pending_conversations',
        'schedule': 300.0,  # Run every 5 minutes (300 seconds)
    },
}

# @app.task(bind=True)
# def debug_task(self):
#     print(f'Request: {self.request!r}')

import api.celery_signals
