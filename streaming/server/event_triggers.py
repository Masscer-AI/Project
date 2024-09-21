from .utils.openai_functions import stream_completion
from server.utils.completions import get_system_prompt
from .utils.apiCalls import save_message
# from .logger import logger


async def on_message_handler(socket_id, data, **kwargs):
    from server.socket import sio

    context = data["context"]
    message = data["message"]
    token = data["token"]
    model = data["model"]
    conversation = data["conversation"]
    print(model, "MODEL TO GENERATE")

    system_prompt = get_system_prompt(context=context)

    data = {}
    ai_response = ""
    async for chunk in stream_completion(system_prompt, message, model=model):
        if isinstance(chunk, str):
            data["chunk"] = chunk
            ai_response += chunk
            await sio.emit("response", data, to=socket_id)

    await sio.emit(
        "responseFinished", {"status": "ok", "ai_response": ai_response}, to=socket_id
    )
    save_message(
        token=token,
        text=message,
        type="user",
        conversation=conversation.get("id", None),
    )
    save_message(
        token=token,
        text=ai_response,
        type="assistant",
        conversation=conversation.get("id", None),
    )


def on_connect_handler(socket_id, **kwargs):
    # sio.emit("available_rooms", room_manager.get_rooms(), to=socket_id)
    pass


async def on_start_handler(socket_id, data, **kwargs):
    print(data)
