import socketio
from .logger import get_custom_logger
from .event_triggers import (
    on_message_handler,
    on_start_handler,
    on_connect_handler,
    on_speech_request_handler,
)


logger = get_custom_logger("socket_manager")


class ProxyNamespaceManager(socketio.AsyncNamespace):
    async def on_start(self, sid, data):
        await on_start_handler(sid, data)

    def on_connect(self, sid, environ):
        logger.info("Environment", environ)
        logger.info(f"Client {sid} connected")
        # return False
        on_connect_handler(socket_id=sid)

    async def on_message(self, sid, message_data):
        logger.debug("RECEIVING MESSAGE EVENT")
        await on_message_handler(socket_id=sid, data=message_data)
        logger.error("Succesfully finished handler execution")

    async def on_speech_request(self, sid, data):
        await on_speech_request_handler(socket_id=sid, data=data)

    def on_test(self, sid, data):
        logger.info(f"data: {data}")
        print("Test", data)

    def on_disconnect(self, sid):
        logger.info(f"Client {sid} disconnected")
