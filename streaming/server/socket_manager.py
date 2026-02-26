import socketio
import json
from .redis_manager import r

from .logger import get_custom_logger
from .event_triggers import (
    on_start_handler,
    on_connect_handler,
    on_test_event_handler,
    on_modify_message_handler,
)


logger = get_custom_logger("socket_manager")


class ProxyNamespaceManager(socketio.AsyncNamespace):
    route_id_to_socket_id = {}
    socket_id_to_route_id = {}

    def _register_route(self, sid, route_id):
        route_id = str(route_id)
        if route_id not in self.route_id_to_socket_id:
            self.route_id_to_socket_id[route_id] = []
        self.route_id_to_socket_id[route_id].append(sid)
        self.socket_id_to_route_id[sid] = route_id
        r.set("route_id_to_socket_id", json.dumps(self.route_id_to_socket_id))
        r.set("socket_id_to_route_id", json.dumps(self.socket_id_to_route_id))

    async def on_start(self, sid, data):
        await on_start_handler(sid, data)

    def on_connect(self, sid, environ):
        logger.info(f"Client {sid} connected")
        on_connect_handler(socket_id=sid)

    def on_register_user(self, sid, user_id):
        self._register_route(sid, user_id)

    def on_register_widget_session(self, sid, route_key):
        if not route_key:
            return
        self._register_route(sid, route_key)

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
        route_id = self.socket_id_to_route_id.get(sid)
        if route_id:
            self.route_id_to_socket_id[route_id].remove(sid)
            if len(self.route_id_to_socket_id[route_id]) == 0:
                del self.route_id_to_socket_id[route_id]
            del self.socket_id_to_route_id[sid]

        r.set("route_id_to_socket_id", json.dumps(self.route_id_to_socket_id))
        r.set("socket_id_to_route_id", json.dumps(self.socket_id_to_route_id))
