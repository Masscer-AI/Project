import redis
import os
import json

from api.utils.color_printer import printer

r = redis.Redis.from_url(os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"))
printer.green(r, "REDIS DJANGO")


def notify_route(route_id, event_type, data):
    data = {
        "route_id": str(route_id),
        "message": data,
        "event_type": event_type,
    }
    r.publish("notifications", json.dumps(data))


def notify_user(user_id, event_type, data):
    notify_route(user_id, event_type, data)
