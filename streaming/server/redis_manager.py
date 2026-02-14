import os
import redis
import asyncio
import json

CHANNEL_NAME = "notifications"


REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
r = redis.Redis.from_url(REDIS_URL)


# Función para escuchar notificaciones
async def listen_to_notifications():
    from .socket import sio

    pubsub = r.pubsub()
    pubsub.subscribe(CHANNEL_NAME)

    while True:
        message = pubsub.get_message()
        if message:
            data = message.get("data")

            if isinstance(data, bytes):
                decoded_message = data.decode("utf-8")
                decoded_message = json.loads(decoded_message)
                user_id_to_emit = decoded_message.get("user_id", None)
                event_type = decoded_message.get("event_type", None)

                if user_id_to_emit and event_type:
                    user_ids_to_socket_id_raw = r.get("user_id_to_socket_id")
                    if user_ids_to_socket_id_raw is None:
                        continue
                    user_ids_to_socket_id = json.loads(user_ids_to_socket_id_raw)

                    sockets = user_ids_to_socket_id.get(str(user_id_to_emit), None)
                    if sockets:
                        for socket in sockets:
                            await sio.emit(event_type, decoded_message, to=socket)

        await asyncio.sleep(0.01)
