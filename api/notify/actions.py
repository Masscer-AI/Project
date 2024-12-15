import redis
import os
import json
# from .models import Notification
from api.utils.color_printer import printer

r = redis.Redis.from_url(os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"))
printer.green(r, "REDIS DJANGO")


def notify_user(user_id, event_type, data):
    # Notification.objects.create(user_id=user_id, message=json.dumps(data))
    data = {
        "user_id": user_id,
        "message": data,
        "event_type": event_type,
    }
    r.publish("notifications", json.dumps(data))
