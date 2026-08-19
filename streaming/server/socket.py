import socketio

from .socket_manager import ProxyNamespaceManager

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    transports=["websocket", "polling"],
    max_http_buffer_size=20 * 1024 * 1024,
)

sio.register_namespace(ProxyNamespaceManager("/"))
