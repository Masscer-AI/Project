import os
from .utils.openai_functions import stream_completion, generate_speech_api
from server.utils.completions import get_system_prompt
from .utils.apiCalls import save_message
import hashlib

from .logger import get_custom_logger

logger = get_custom_logger("event_triggers")


async def on_message_handler(socket_id, data, **kwargs):
    from server.socket import sio

    context = data["context"]
    message = data["message"]
    token = data["token"]
    model = data.get("model", {"name": "gpt-4o-mini", "provider": "openai"})
    conversation = data["conversation"]

    system_prompt = get_system_prompt(context=context)

    data = {}
    ai_response = ""
    async for chunk in stream_completion(
        system_prompt, message["text"], model=model, attachments=message["attachments"]
    ):
        if isinstance(chunk, str):
            data["chunk"] = chunk
            ai_response += chunk
            await sio.emit("response", data, to=socket_id)

    await sio.emit(
        "responseFinished", {"status": "ok", "ai_response": ai_response}, to=socket_id
    )
    save_message(
        message=message,
        conversation=conversation.get("id", None),
        token=token,
    )
    save_message(
        message={"type": "assistant", "text": ai_response, "attachments": []},
        conversation=conversation.get("id", None),
        token=token,
    )


def on_connect_handler(socket_id, **kwargs):
    # sio.emit("available_rooms", room_manager.get_rooms(), to=socket_id)
    pass


async def on_start_handler(socket_id, data, **kwargs):
    print(data)


AUDIO_DIR = "audios"


async def on_speech_request_handler(socket_id, data, **kwargs):

    logger.debug("Generating speech with socket")

    from server.socket import sio

    text = data["text"]
    logger.debug(f"TEXT to SPEECH {text}")

    # Hash the text to obtain a unique value
    hashed_text = hashlib.md5(text.encode()).hexdigest()

    output_path = os.path.join(AUDIO_DIR, f"{hashed_text}.mp3")

    # Check if the audio file already exists
    if os.path.exists(output_path):
        logger.debug("Audio file already exists, sending existing file.")
        with open(output_path, "rb") as audio_file:
            audio_content = audio_file.read()
            await sio.emit("audio-file", audio_content, to=socket_id)
    else:
        for chunk in generate_speech_api(text=text, output_path=output_path):
            logger.debug("audio emitted!")
            await sio.emit("audio-chunk", chunk, to=socket_id)

        with open(output_path, "rb") as audio_file:
            audio_content = audio_file.read()
            await sio.emit("audio-file", audio_content, to=socket_id)
