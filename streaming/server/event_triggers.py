import os
from .utils.openai_functions import stream_completion, generate_speech_api

# from server.utils.completions import get_system_prompt
from .utils.apiCalls import save_message, get_results
from .utils.brave_search import search_brave
import hashlib
from .utils.apiCalls import get_system_prompt
from .logger import get_custom_logger

logger = get_custom_logger("event_triggers")


async def on_message_handler(socket_id, data, **kwargs):
    from server.socket import sio

    context = data["context"]
    message = data["message"]
    web_search_activated = data.get("web_search_activated", False)
    models_to_complete = data.get("models_to_complete", [])

    token = data["token"]
    agent_slug = data.get("agent_slug", "useful-assistant")

    model = data.get("model", {"name": "gpt-4o-mini", "provider": "openai"})
    conversation = data["conversation"]

    rag_results = get_results(
        query_text=message["text"],
        agent_slug=agent_slug,
        token=token,
        conversation_id=conversation["id"],
    )

    documents_context = ""
    complete_context = context

    if rag_results is not None:
        documents = rag_results["results"]["documents"]
        for d in documents:
            if len(d) > 0:
                documents_context += d[0]

        if len(documents_context) > 0:
            complete_context += f"\n\nThe following is information about a vector storage querying the user message: ---start_vector_context\n\n{documents_context}\n\n---end_vector_context---"

    if web_search_activated:
        print("Emitting notification")
        await sio.emit(
            "notification",
            {"message": "Exploring the web to add more context to your message"},
            to=socket_id,
        )
        web_result = search_brave(message["text"])
        complete_context += f"\n\nThe following context comes from a web search using the user message as query \n{web_result}. END OF WEB SEARCH RESULTS\n"

    for m in models_to_complete:
        print(m["slug"], "SLUG OF MODEL TO COMPLETE")
        
    system_prompt = get_system_prompt(
        context=complete_context, agent_slug=agent_slug, token=token
    )

    data = {}
    ai_response = ""

    async for chunk in stream_completion(
        system_prompt, message["text"], model=model, attachments=[]
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
