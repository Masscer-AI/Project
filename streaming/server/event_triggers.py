from .logger import get_custom_logger

logger = get_custom_logger("event_triggers")


def on_connect_handler(socket_id, **kwargs):
    pass


async def on_start_handler(socket_id, data, **kwargs):
    print(data)


async def on_test_event_handler(socket_id, data, **kwargs):
    from server.socket import sio

    print("Test event received")

    await sio.emit(
        "notification",
        {"message": "Exploring the web to add more context to your message"},
        to=socket_id,
    )


async def on_modify_message_handler(socket_id, data, **kwargs):
    print(data)
