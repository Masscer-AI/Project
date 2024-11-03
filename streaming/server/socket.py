# server/socket.py
import socketio
import os

# Register the namespace
from .socket_manager import ProxyNamespaceManager


cors_allowed_origins = os.getenv("CORS_ORIGINS", "*").split(",")

print(cors_allowed_origins, "From fastAPI SOCKET ")

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    transports=["websocket", "polling"],
    # logger=True,
    # engineio_logger=True,
    max_http_buffer_size=20 * 1024 * 1024,
)

sio.register_namespace(ProxyNamespaceManager("/"))
