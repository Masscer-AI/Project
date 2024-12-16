import os
import json
from datetime import datetime
from .utils.openai_functions import stream_completion, generate_speech_api

from .utils.apiCalls import (
    save_message,
    regenerate_conversation,
    query_document,
    query_completions,
)
from .utils.brave_search import new_search_brave
import hashlib
from .utils.apiCalls import get_system_prompt
from .logger import get_custom_logger

logger = get_custom_logger("event_triggers")


def extract_rag_results(rag_results, context):
    documents_context = ""
    complete_context = context
    counter = 0
    added_sources = []
    sources = []
    if rag_results is not None:
        metadatas = rag_results["results"]["metadatas"]
        for meta in metadatas:
            for ref in meta:
                if len(ref) > 0:
                    if ref in added_sources:
                        continue

                    sources.append(ref)
                    added_sources.append(ref)

                    documents_context += f"<vector vector_href='#{ref.get('model_name', 'chunk')}-{ref.get('model_id', 132132)}'>{ref.get('content', '')}</vector>"
                    counter += 1

        if len(documents_context) > 0:
            complete_context += f"""\n
The following information comes from a vector storage of embeddings the user has saved previously. You can use this information to enrich your responses. 
            
Each <vector>[vector content]</vector> XML like tag contains information for a single vector embedding.
            
            {documents_context}
            
            If you use information from the vector storage, please cite the resources your are using using an anchor tag with the vector_href attribute inside.
            For example: <a href='#chunk-CHUNK_ID' >SOME_RELATED_CONECTOR</a> where SOME_RELATED_CONECTOR is a three-four words text related to the chunk content that the user will be able to review. You can add the sources in any place of your response. Add as many as needed. You must cite the source using the href, the SOME_RELATED_CONECTOR is generated by you.
            """

    return complete_context, sources


async def on_message_handler(socket_id, data, **kwargs):
    now = datetime.now()
    current_date_time = now.strftime("%Y-%m-%d %H:%M:%S")
    from server.socket import sio

    await sio.emit(
        "generation_status",
        {"message": "message-received"},
        to=socket_id,
    )

    prev_messages = data["context"]
    message = data["message"]

    token = data["token"]
    conversation = data["conversation"]
    web_search_activated = data.get("web_search_activated", False)
    use_rag = data["use_rag"]
    message["conversation"] = conversation.get("id", None)
    multi_agentic_modality = data.get("multiagentic_modality", "isolated")

    attachments = message.get("attachments", [])
    attachments_context = ""
    source_documents = []

    user_id_to_emit = message.get("id", None)

    for a in attachments:
        extraction_mode = a.get("mode", None)

        if a.get("type", None) == "image":
            continue

        if extraction_mode and extraction_mode == "similar_chunks":
            rag_results = query_document(
                query_text=message["text"],
                token=token,
                conversation_id=conversation["id"],
                document_id=a.get("id", None),
            )
            await sio.emit(
                "generation_status",
                {"message": "searching-similar-information-in-the-database"},
                to=socket_id,
            )

            attachments_context, sources = extract_rag_results(
                rag_results, attachments_context
            )
            source_documents.extend(sources)
        if extraction_mode and extraction_mode == "all_possible_text":
            doc_content = f"""
            <Document name="{a.get("name", "No name received")}" extra-info-for-ai="The user added this document to its prompt">
                    {a.get("text", "No content received")[:40000]}
            </Document> 
            """
            attachments_context += f"\n\n{doc_content}\n\n"
            await sio.emit(
                "generation_status",
                {
                    "message": "appending-all-document-text",
                    "extra": a.get("name", " No name received"),
                },
                to=socket_id,
            )

    web_results = []
    use_rag = data.get("use_rag", False)
    if web_search_activated:

        await sio.emit(
            "generation_status",
            {"message": "exploring-the-web"},
            to=socket_id,
        )
        serializables_prev_messages = [
            {"text": m["text"], "type": m["type"]} for m in prev_messages
        ]

        web_results = new_search_brave(
            message["text"],
            json.dumps(
                {
                    "messages": serializables_prev_messages,
                    "other_context": attachments_context,
                }
            ),
        )
        await sio.emit(
            "generation_status",
            {"message": "web-explored-successfully"},
            to=socket_id,
        )

    regenerate = data.get("regenerate", None)

    agents_to_complete = data.get(
        "models_to_complete",
        [],
    )

    if not regenerate:
        user_message_res = save_message(
            message=message,
            token=token,
        )
        user_id_to_emit = user_message_res["id"]

    else:
        regenerate_conversation(
            conversation_id=conversation["id"],
            user_message_id=regenerate["user_message_id"],
            token=token,
        )
        # user_id_to_emit = regenerate["user_message_id"]

    versions = []

    for index, m in enumerate(agents_to_complete, start=1):
        # If there are previous versions, we need to add them to the context

        if multi_agentic_modality == "grupal":
            prev_generations = [
                {
                    "text": v["text"],
                    "agent_name": v["agent_name"],
                    "type": "prev_ai",
                }
                for v in versions
            ]
            prev_messages.extend(prev_generations)

        agent_slug = m["slug"]
        version = {
            "agent_slug": agent_slug,
            "agent_name": m["name"],
            "type": "assistant",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "sources": source_documents,
        }
        complete_context = ""

        if attachments_context:
            complete_context += f"The following information is from the a vector store, if is empty, then it means the user is still not using the vector store: <vector_store_context>{attachments_context}</vector_store_context>\n\n"
        else:
            print("No attachments context found to append")

        complete_context += f"The current date and time is {current_date_time}\n\n"

        if use_rag:
            print("try to add completions for the AGENT")
            await sio.emit(
                "generation_status",
                {"message": "querying-completions-for-the-agent"},
                to=socket_id,
            )
            completions = query_completions(
                query_text=message["text"],
                agent_slug=agent_slug,
                prev_messages=prev_messages,
                token=token,
            )
            if completions and len(completions) > 0:
                complete_context, sources = extract_rag_results(
                    completions, complete_context
                )
                source_documents.extend(sources)
            else:
                print("No completions found for the agent")
        if len(web_results) > 0:
            complete_context += f"\n<web_search_results>\n{json.dumps(web_results)}\n </web_search_results>\n"
        else:
            print("No web results found")

        system_prompt = get_system_prompt(
            context=complete_context, agent_slug=agent_slug, token=token
        )
        system_prompt += f"\n\nYour name is: {m['name']}."

        data = {"agent_slug": agent_slug}
        ai_response = ""

        m["multiagentic_modality"] = multi_agentic_modality

        await sio.emit(
            "generation_status",
            {
                "message": "generating-response-with",
                "extra": f" {m["name"]} ({m["llm"]["slug"]})",
            },
            to=socket_id,
        )
        async for chunk in stream_completion(
            system_prompt,
            message["text"],
            model=m["llm"],
            attachments=message["attachments"],
            config=m,
            prev_messages=prev_messages,
            agent_slug=m["slug"],
        ):
            if isinstance(chunk, str):
                data["chunk"] = chunk
                ai_response += chunk

                await sio.emit(
                    f"response-for-{message['index'] + index }", data, to=socket_id
                )
                await sio.emit("response", {}, to=socket_id)

            else:
                print("Chunk received", chunk)
                version["usage"] = {
                    "completion_tokens": chunk.completion_tokens,
                    "prompt_tokens": chunk.prompt_tokens,
                    "total_tokens": chunk.total_tokens,
                    "model_slug": m["llm"]["slug"],
                }

        version["web_search_results"] = web_results
        version["text"] = ai_response
        versions.append(version)

        if multi_agentic_modality == "grupal":
            ai_message_res = save_message(
                message={
                    "type": "assistant",
                    "text": version["text"],
                    "attachments": [],
                    "conversation": conversation.get("id", None),
                    "versions": [version],
                },
                token=token,
            )
            await sio.emit(
                "responseFinished",
                {
                    "status": "ok",
                    "versions": [version],
                    "user_message_id": user_id_to_emit,
                    "ai_message_id": ai_message_res["id"],
                    "next_agent_slug": (
                        agents_to_complete[index]["slug"]
                        if index < len(agents_to_complete)
                        else None
                    ),
                },
                to=socket_id,
            )

    if multi_agentic_modality == "isolated":
        ai_message_res = save_message(
            message={
                "type": "assistant",
                "text": versions[0]["text"],
                "attachments": [],
                "conversation": conversation.get("id", None),
                "versions": versions,
            },
            token=token,
        )
        await sio.emit(
            "responseFinished",
            {
                "status": "ok",
                "versions": versions,
                "user_message_id": user_id_to_emit,
                "ai_message_id": ai_message_res["id"],
            },
            to=socket_id,
        )

    await sio.emit(
        "generation_status",
        {"message": "message-ready"},
        to=socket_id,
    )


def on_connect_handler(socket_id, **kwargs):
    pass


async def on_start_handler(socket_id, data, **kwargs):

    print(data)


AUDIO_DIR = "audios"


async def on_speech_request_handler(socket_id, data, **kwargs):
    audio_format = data.get("format", "wav")
    logger.debug("Generating speech with socket", data)

    from server.socket import sio

    text = data.get("text", "")
    id_to_emit = data.get("id", None)
    voice = data.get("voice", None)

    if not id_to_emit or not voice or not text:
        logger.error("Missing data to generate speech", data)
        return

    hashed_text = hashlib.md5(text.encode()).hexdigest()

    output_path = os.path.join(AUDIO_DIR, f"{hashed_text}.{audio_format}")

    if os.path.exists(output_path):
        logger.debug("Audio file already exists, sending existing file.")
        with open(output_path, "rb") as audio_file:
            audio_content = audio_file.read()
            await sio.emit(f"audio-file-{id_to_emit}", audio_content, to=socket_id)
    else:
        counter = 0

        # audio = b""
        for chunk in generate_speech_api(
            text=text,
            output_path=output_path,
            voice=voice.get("slug", "alloy"),
            output_format=audio_format,
        ):
            # audio += chunk
            # data = {
            #     "audio_bytes": audio,
            #     "position": counter,
            # }

            # if len(audio) > 104857:
            #     await sio.emit(f"audio-chunk-{id_to_emit}", data, to=socket_id)
            #     audio = b""
            # logger.debug("audio chunk emitted!")
            counter += 1

        logger.debug("Audio generation finished!")
        logger.debug(f"Number of chunks: {counter}")

        with open(output_path, "rb") as audio_file:
            audio_content = audio_file.read()
            await sio.emit(f"audio-file-{id_to_emit}", audio_content, to=socket_id)


async def on_test_event_handler(socket_id, data, **kwargs):
    # context = "This i an example query, just make your best effort"

    from server.socket import sio

    print(
        "Test event received",
    )
    # if True:

    await sio.emit(
        "notification",
        {"message": "Exploring the web to add more context to your message"},
        to=socket_id,
    )
    # web_results = new_search_brave(data["query"], json.dumps(context))

    # version["web_search_results"] = web_results
    # complete_context += f"\n\<web_search_results>\n{json.dumps(web_results)}\n </web_search_results>\n"


async def on_modify_message_handler(socket_id, data, **kwargs):
    print(data)
