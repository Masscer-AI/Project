import socketio
import json
from .redis_manager import r

from .logger import get_custom_logger
from .event_triggers import (
    on_message_handler,
    on_start_handler,
    on_connect_handler,
    on_speech_request_handler,
    on_test_event_handler,
    on_modify_message_handler,
)


logger = get_custom_logger("socket_manager")


class ProxyNamespaceManager(socketio.AsyncNamespace):
    user_id_to_socket_id = {}
    socket_id_to_user_id = {}

    async def on_start(self, sid, data):
        await on_start_handler(sid, data)

    def on_connect(self, sid, environ):
        # QUERY_STRING = environ.get("QUERY_STRING")

        logger.info(f"Client {sid} connected")
        # return False
        on_connect_handler(socket_id=sid)

    def on_register_user(self, sid, user_id):
        if user_id not in self.user_id_to_socket_id:
            self.user_id_to_socket_id[user_id] = []
        self.user_id_to_socket_id[user_id].append(sid)

        self.socket_id_to_user_id[sid] = user_id
        # Save a copy of the user_id_to_socket_id in redis
        r.set("user_id_to_socket_id", json.dumps(self.user_id_to_socket_id))
        r.set("socket_id_to_user_id", json.dumps(self.socket_id_to_user_id))

    async def on_message(self, sid, message_data):
        logger.info(f"Message received from client {sid}")
        try:
            await on_message_handler(socket_id=sid, data=message_data)
        except Exception as e:
            logger.error(f"Error processing message from {sid}: {e}", exc_info=True)
            from server.socket import sio
            await sio.emit("error", {"message": f"Error processing message: {str(e)}"}, to=sid)

    async def on_speech_request(self, sid, data):
        await on_speech_request_handler(socket_id=sid, data=data)

    async def on_test_event(self, sid, data):
        await on_test_event_handler(socket_id=sid, data=data)
        return "testing ack"

    async def on_modify_message(self, sid, data):
        await on_modify_message_handler(socket_id=sid, data=data)

    def on_test(self, sid, data):
        logger.info(f"data: {data}")
        print("Test", data)

    def on_disconnect(self, sid):
        logger.info(f"Client {sid} disconnected")
        user_id = self.socket_id_to_user_id.get(sid)
        if user_id:
            self.user_id_to_socket_id[user_id].remove(sid)
            if len(self.user_id_to_socket_id[user_id]) == 0:
                del self.user_id_to_socket_id[user_id]
            del self.socket_id_to_user_id[sid]

        # Save a copy of the user_id_to_socket_id in redis
        r.set("user_id_to_socket_id", json.dumps(self.user_id_to_socket_id))
        r.set("socket_id_to_user_id", json.dumps(self.socket_id_to_user_id))
