import json
import os

import redis

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(
            os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        )
    return _redis_client


def notify_route(route_id, event_type, data):
    data = {
        "route_id": str(route_id),
        "message": data,
        "event_type": event_type,
    }
    _get_redis().publish("notifications", json.dumps(data))


def notify_user(user_id, event_type, data):
    notify_route(user_id, event_type, data)
