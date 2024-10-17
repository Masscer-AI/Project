import os
from .utils.openai_functions import stream_completion, generate_speech_api

# from server.utils.completions import get_system_prompt
from .utils.apiCalls import save_message, get_results
from .utils.brave_search import search_brave
import hashlib
from .utils.apiCalls import get_system_prompt
from .logger import get_custom_logger

logger = get_custom_logger("event_triggers")


def extract_rag_results(rag_results, context):
    documents_context = ""
    complete_context = context
    counter = 0
    if rag_results is not None:
        metadatas = rag_results["results"]["metadatas"]
        for meta in metadatas:
            for ref in meta:
                if len(ref) > 0:
                    print(counter, ref["chunk_id"])
                    documents_context += f"DOCUMENT_ID: {ref["document_id"]}\nCHUNK_ID: {ref["chunk_id"]}\nCHUNK CONTENT: {ref["content"]}"
                    counter += 1

        if len(documents_context) > 0:
            complete_context += f"\n\nThe following is information about a embeddings vector storage querying the user message: ---start_vector_context\n\n{documents_context}\n\n---end_vector_context---\nIf you use information from the vector storage, please cite the resourcess in anchor tags like: <a href='#chunk-CHUNK_ID' target='__blank'>some_related_text</a> where CHUNK_ID is the ID of the chunks you are using to generate that part of the response and some_related_text is a three-four words text related to the chunk content that the user will be able to review. You can add the sources in any place of your response. Add as many as needed."

    return complete_context


async def on_message_handler(socket_id, data, **kwargs):
    from server.socket import sio

    context = data["context"]
    message = data["message"]
    web_search_activated = data.get("web_search_activated", False)
    use_rag = data.get("use_rag", False)
    models_to_complete = data.get("models_to_complete", [])

    token = data["token"]

    conversation = data["conversation"]
 
    save_message(
        message=message,
        conversation=conversation.get("id", None),
        token=token,
    )

    for m in models_to_complete:
        agent_slug = m["slug"]
        complete_context = context
        if use_rag:
            await sio.emit(
                "notification",
                {"message": "Searching relevant information in the documents"},
                to=socket_id,
            )
            rag_results = get_results(
                query_text=message["text"],
                agent_slug=agent_slug,
                token=token,
                conversation_id=conversation["id"],
            )
            complete_context = extract_rag_results(rag_results, complete_context)

        if web_search_activated:
            print("Emitting notification")
            await sio.emit(
                "notification",
                {"message": "Exploring the web to add more context to your message"},
                to=socket_id,
            )
            web_result = search_brave(message["text"], context)
            complete_context += f"\n\nThe following context comes from a web search using the user message as query \n{web_result}. END OF WEB SEARCH RESULTS\n"

        system_prompt = get_system_prompt(
            context=complete_context, agent_slug=agent_slug, token=token
        )

        data = {"agent_slug": agent_slug}
        ai_response = ""

        async for chunk in stream_completion(
            system_prompt,
            message["text"],
            model=m["llm"],
            attachments=message["attachments"],
            config=m,
        ):
            if isinstance(chunk, str):
                data["chunk"] = chunk
                ai_response += chunk
                await sio.emit("response", data, to=socket_id)

        await sio.emit(
            "responseFinished",
            {"status": "ok", "ai_response": ai_response},
            to=socket_id,
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
