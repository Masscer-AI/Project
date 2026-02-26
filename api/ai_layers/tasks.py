import logging
import time
import traceback as tb
import json
import re
from celery import shared_task
from .actions import generate_agent_profile_picture

logger = logging.getLogger(__name__)


def _serialize_prev_messages(conversation, before_message_id, limit=50):
    """Load and serialize prev messages for reproducibility."""
    from api.messaging.models import Message

    qs = Message.objects.filter(
        conversation=conversation,
        id__lt=before_message_id,
    ).order_by("-id")[:limit]
    return [
        {
            "id": m.id,
            "type": m.type,
            "text": m.text,
            "versions": m.versions,
            "attachments": m.attachments or [],
        }
        for m in reversed(list(qs))
    ]


@shared_task
def async_generate_agent_profile_picture(agent_id: int):
    result = generate_agent_profile_picture(agent_id)
    return result


def _build_user_message_text(user_inputs: list[dict]) -> str:
    """
    Build a plain-text user message from user_inputs.
    Only includes input_text; images and documents are referenced via attachments/tool.
    """
    parts = []
    for inp in user_inputs:
        if inp.get("type") == "input_text":
            text = inp.get("text", "").strip()
            if text:
                parts.append(text)
    return "\n".join(parts) if parts else ""


def _format_attachments_for_model_context(attachments: list[dict]) -> str:
    """
    Render attachment metadata as plain text for model context.

    This is used when building the AgentLoop inputs so the model can discover
    attachment IDs from previous turns, without mutating stored Message.text.
    """
    if not attachments:
        return ""

    lines = ["Attachments available from this message:"]
    for a in attachments:
        a_type = a.get("type") or "attachment"
        aid = a.get("attachment_id") or a.get("id") or ""
        name = a.get("name") or ""
        url = a.get("content") if a_type == "website" else ""

        bits = [a_type]
        if name:
            bits.append(f"name={name}")
        if url:
            bits.append(f"url={url}")
        if aid:
            bits.append(f"attachment_id={aid}")
        lines.append("- " + " | ".join(bits))

    return "\n".join(lines)


def _build_agent_loop_inputs(
    *,
    prev_messages: list[dict],
    current_user_text: str,
    current_user_attachments: list[dict],
    agent_slug: str,
    multiagentic_modality: str,
) -> list[dict]:
    """
    Build the ordered OpenAI input messages for AgentLoop, including previous turns.

    We include attachment metadata inside the message content so the model can
    reference attachment IDs across many turns.
    """
    inputs: list[dict] = []

    for m in prev_messages or []:
        m_type = m.get("type")
        attachments_block = _format_attachments_for_model_context(m.get("attachments") or [])

        if m_type == "user":
            text = m.get("text") or ""
            if attachments_block:
                text = f"{text}\n\n{attachments_block}"
            inputs.append({"role": "user", "content": text})
            continue

        if m_type == "assistant":
            versions = m.get("versions") or []

            if multiagentic_modality == "grupal" and versions:
                for v in versions:
                    v_text = v.get("text") or ""
                    if not v_text:
                        continue
                    if v.get("agent_slug") == agent_slug:
                        text = v_text
                        if attachments_block:
                            text = f"{text}\n\n{attachments_block}"
                        inputs.append({"role": "assistant", "content": text})
                    else:
                        agent_name = v.get("agent_name", "Unknown")
                        tagged = (
                            f"[GROUP CHAT — message from AI assistant \"{agent_name}\"]\n\n"
                            f"{v_text}"
                        )
                        if attachments_block:
                            tagged = f"{tagged}\n\n{attachments_block}"
                        inputs.append({"role": "user", "content": tagged})
                continue

            # isolated: pick this agent's version if present, else fall back to message text
            picked = None
            for v in versions:
                if v.get("agent_slug") == agent_slug and v.get("text"):
                    picked = v.get("text")
                    break
            text = picked or (m.get("text") or "")
            if attachments_block:
                text = f"{text}\n\n{attachments_block}"
            inputs.append({"role": "assistant", "content": text})
            continue

    # Current user turn (last)
    final_text = current_user_text or ""
    current_block = _format_attachments_for_model_context(current_user_attachments or [])
    if current_block:
        final_text = f"{final_text}\n\n{current_block}"
    inputs.append({"role": "user", "content": final_text})

    return inputs


def _resolve_user_inputs_and_attachments(
    user_inputs: list[dict],
    conversation_id: str | None = None,
):
    """
    Normalize user_inputs to the minimal agent-task contract:
    - input_text
    - input_attachment { attachment_id }

    Also builds Message.attachments JSON for display and returns MessageAttachment
    objects to link to the saved Message.
    """
    from api.messaging.models import MessageAttachment
    from django.conf import settings

    resolved: list[dict] = []
    message_attachments: list[dict] = []
    attachment_objects: list[MessageAttachment] = []

    def _display_url_for_file(att: MessageAttachment) -> str:
        if not att.file:
            return ""
        api_base = getattr(settings, "API_BASE_URL", None) or ""
        url = att.file.url
        if api_base and not url.startswith("http"):
            return f"{api_base.rstrip('/')}{url}"
        return url

    for inp in user_inputs:
        input_type = inp.get("type", "")

        if input_type == "input_text":
            resolved.append({"type": "input_text", "text": inp.get("text", "")})
            continue

        if input_type == "input_attachment":
            attachment_id = inp.get("attachment_id")
            if not attachment_id:
                raise ValueError("input_attachment requires attachment_id")
            try:
                if conversation_id:
                    att = MessageAttachment.objects.get(
                        id=attachment_id,
                        conversation_id=conversation_id,
                    )
                else:
                    att = MessageAttachment.objects.get(id=attachment_id)
            except MessageAttachment.DoesNotExist:
                raise ValueError(
                    f"MessageAttachment {attachment_id} not found"
                    + (f" for conversation {conversation_id}" if conversation_id else "")
                )

            attachment_objects.append(att)
            resolved.append({"type": "input_attachment", "attachment_id": str(att.id)})

            # Attachments shown in Message history (UI)
            kind = getattr(att, "kind", "") or ""
            if kind == "website":
                message_attachments.append(
                    {
                        "type": "website",
                        "content": getattr(att, "url", "") or "",
                        "attachment_id": str(att.id),
                    }
                )
            elif kind == "rag_document":
                rag_doc = getattr(att, "rag_document", None)
                message_attachments.append(
                    {
                        "type": "rag_document",
                        "name": getattr(rag_doc, "name", None) if rag_doc else None,
                        "attachment_id": str(att.id),
                    }
                )
            else:
                # Default: file attachment (image or generic document)
                display_url = _display_url_for_file(att)
                is_image = bool(att.content_type and att.content_type.startswith("image/"))
                filename = (
                    att.file.name.split("/")[-1]
                    if att.file and att.file.name
                    else ("image" if is_image else "document")
                )
                message_attachments.append(
                    {
                        "type": "image" if is_image else "document",
                        "content": display_url,
                        "name": filename,
                        "attachment_id": str(att.id),
                    }
                )
            continue

        raise ValueError(f"Unsupported user input type '{input_type}'")

    return resolved, message_attachments, attachment_objects


def _extract_create_image_attachments(tool_calls: list[dict]) -> tuple[list[dict], list[str]]:
    """
    Extract image attachment descriptors from AgentLoop tool_calls.

    create_image tool returns JSON like:
      { attachment_id, name, content, ... }

    We persist those into Message.attachments (for UI) and keep attachment IDs
    to link MessageAttachment.message after the assistant Message exists.
    """
    if not tool_calls:
        return [], []

    attachments: list[dict] = []
    attachment_ids: list[str] = []

    for call in tool_calls:
        try:
            if (call or {}).get("tool_name") != "create_image":
                continue
            raw = (call or {}).get("result") or ""
            if not isinstance(raw, str) or not raw.strip():
                continue
            data = json.loads(raw)
            if not isinstance(data, dict):
                continue
            aid = data.get("attachment_id")
            content = data.get("content") or ""
            name = data.get("name") or "image"
            if not aid or not content:
                continue
            attachments.append(
                {
                    "type": "image",
                    "content": content,
                    "name": name,
                    "attachment_id": str(aid),
                }
            )
            attachment_ids.append(str(aid))
        except Exception:
            # Never fail the whole agent task because of attachment parsing
            continue

    return attachments, attachment_ids


def _extract_create_speech_attachments(tool_calls: list[dict]) -> tuple[list[dict], list[str]]:
    """
    Extract audio attachment descriptors from AgentLoop tool_calls.

    create_speech tool returns JSON like:
      { attachment_id, name, content, content_type, ... }
    """
    if not tool_calls:
        return [], []

    attachments: list[dict] = []
    attachment_ids: list[str] = []

    for call in tool_calls:
        try:
            if (call or {}).get("tool_name") != "create_speech":
                continue
            raw = (call or {}).get("result") or ""
            if not isinstance(raw, str) or not raw.strip():
                continue
            data = json.loads(raw)
            if not isinstance(data, dict):
                continue
            aid = data.get("attachment_id")
            content = data.get("content") or ""
            name = data.get("name") or "speech"
            if not aid or not content:
                continue
            attachments.append(
                {
                    "type": "audio_generation",
                    "content": content,
                    "name": name,
                    "attachment_id": str(aid),
                }
            )
            attachment_ids.append(str(aid))
        except Exception:
            continue

    return attachments, attachment_ids


def _message_attachment_to_display_dict(att) -> dict | None:
    """
    Build a Message.attachments-compatible descriptor from a MessageAttachment row.
    """
    from django.conf import settings

    kind = getattr(att, "kind", "") or ""
    aid = str(att.id)

    if kind == "website":
        return {
            "type": "website",
            "content": getattr(att, "url", "") or "",
            "attachment_id": aid,
        }

    if kind == "rag_document":
        rag_doc = getattr(att, "rag_document", None)
        return {
            "type": "rag_document",
            "name": getattr(rag_doc, "name", None) if rag_doc else None,
            "attachment_id": aid,
        }

    # Default: file-like attachment
    file_field = getattr(att, "file", None)
    if not file_field:
        return None

    url = file_field.url
    api_base = getattr(settings, "API_BASE_URL", None) or ""
    if api_base and isinstance(url, str) and not url.startswith("http"):
        url = f"{api_base.rstrip('/')}{url}"

    ctype = getattr(att, "content_type", "") or ""
    if ctype.startswith("image/"):
        att_type = "image"
    elif ctype.startswith("audio/"):
        att_type = "audio_generation"
    else:
        att_type = "document"

    filename = (
        file_field.name.split("/")[-1]
        if getattr(file_field, "name", None)
        else ("image" if att_type == "image" else "document")
    )

    return {
        "type": att_type,
        "content": url,
        "name": filename,
        "attachment_id": aid,
    }


def _extract_referenced_attachments_from_text(
    text: str,
    conversation_id: str,
) -> list[dict]:
    """
    Resolve attachment:<uuid> references found in assistant output text and return
    their display descriptors so frontend markdown rendering can resolve them.
    """
    if not text:
        return []

    ids = re.findall(
        r"attachment:([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
        text,
    )
    if not ids:
        return []

    # Keep mention order but dedupe.
    ordered_ids: list[str] = []
    seen: set[str] = set()
    for aid in ids:
        if aid in seen:
            continue
        seen.add(aid)
        ordered_ids.append(aid)

    from api.messaging.models import MessageAttachment

    rows = MessageAttachment.objects.filter(
        conversation_id=conversation_id,
        id__in=ordered_ids,
    )
    by_id = {str(r.id): r for r in rows}

    resolved: list[dict] = []
    for aid in ordered_ids:
        row = by_id.get(aid)
        if not row:
            continue
        descriptor = _message_attachment_to_display_dict(row)
        if descriptor:
            resolved.append(descriptor)
    return resolved


def _extract_rag_sources(tool_calls: list[dict]) -> list[dict]:
    """
    Extract RAG sources from rag_query tool calls so they can be displayed
    in the frontend just like the streaming path does.

    Returns a list of source dicts matching the TSource frontend type:
      { model_id, model_name, content, extra }
    """
    if not tool_calls:
        return []

    sources: list[dict] = []
    seen: set[str] = set()

    for call in tool_calls:
        try:
            if (call or {}).get("tool_name") != "rag_query":
                continue
            raw = (call or {}).get("result") or ""
            if not isinstance(raw, str) or not raw.strip():
                continue
            data = json.loads(raw)
            if not isinstance(data, dict):
                continue
            results_wrapper = data.get("results") or {}
            inner = results_wrapper.get("results") or results_wrapper
            metadatas = inner.get("metadatas") or []
            for meta_list in metadatas:
                for meta in meta_list:
                    if not isinstance(meta, dict) or not meta:
                        continue
                    key = f"{meta.get('model_name', '')}-{meta.get('model_id', '')}"
                    if key in seen:
                        continue
                    seen.add(key)
                    sources.append({
                        "model_id": meta.get("model_id"),
                        "model_name": meta.get("model_name", "chunk"),
                        "content": meta.get("content", ""),
                        "extra": meta.get("extra", ""),
                    })
        except Exception:
            continue

    return sources


@shared_task
def conversation_agent_task(
    conversation_id: str,
    user_inputs: list[dict],
    tool_names: list[str],
    agent_slugs: list[str],
    plugin_slugs: list[str] | None = None,
    multiagentic_modality: str = "isolated",
    max_iterations: int = 10,
    user_id: int | str | None = None,
    regenerate_message_id: int | None = None,
):
    """
    Celery task that runs an AgentLoop for one or more agents in a conversation.

    Resolves agents from their slugs, derives instructions and model for each,
    executes the agent loop for each (sequentially), and emits real-time status
    updates via Redis pub/sub (notify_user) so the frontend can show progress.

    For multiagentic_modality="grupal", each agent sees previous agents' outputs
    as context. For "isolated", each agent only sees the user message.

    Args:
        conversation_id: UUID of the conversation
        user_inputs: list of input dicts, e.g. [{"type": "input_text", "text": "..."}]
        tool_names: list of tool names to resolve from the registry
        agent_slugs: list of Agent slugs to run (in order)
        multiagentic_modality: "isolated" or "grupal"
        user_id: Notification route id (user id or widget_session:<id>)
        regenerate_message_id: if set, reuse this user message (update its text,
            delete all subsequent messages) instead of creating a new one.

    Returns:
        dict with status, output, iterations, tool_calls_count, message_id
    """
    from api.ai_layers.agent_loop import AgentLoop
    from api.ai_layers.models import Agent, AgentSession
    from api.ai_layers.plugins import format_available_plugins_summary
    from api.ai_layers.tools import resolve_tools
    from api.ai_layers.schemas import (
        AgentSessionInputs,
        AgentSessionOutputs,
        AgentRef,
        ModelRef,
        OutputValue,
        OutputError,
    )
    from api.notify.actions import notify_user
    from api.messaging.models import Conversation, Message
    notification_route_id = user_id
    actor_user_id = user_id if isinstance(user_id, int) else None

    # Get conversation first (needed for validation in resolve)
    try:
        conversation = Conversation.objects.get(id=conversation_id)
    except Conversation.DoesNotExist:
        logger.error("Conversation %s not found", conversation_id)
        notify_user(
            notification_route_id,
            "agent_events_channel",
            {"type": "error", "conversation_id": conversation_id, "error": f"Conversation {conversation_id} not found"},
        )
        return {"status": "error", "error": "Conversation not found"}

    # plugin_slugs is no longer used — plugins are now auto-discovered
    # by the agent via the read_plugin_instructions tool.

    # Normalize inputs and collect attachments for Message (strict contract)
    try:
        resolved_inputs, message_attachments, attachment_objects = _resolve_user_inputs_and_attachments(
            user_inputs, conversation_id=conversation_id
        )
    except ValueError as e:
        notify_user(
            notification_route_id,
            "agent_events_channel",
            {"type": "error", "conversation_id": conversation_id, "error": str(e)},
        )
        return {"status": "error", "error": str(e)}
    user_message_text = _build_user_message_text(resolved_inputs)

    def emit_event(event_type: str, data: dict) -> None:
        payload = {"type": event_type, "conversation_id": conversation_id, **data}
        notify_user(notification_route_id, "agent_events_channel", payload)

    def emit_finished(data: dict) -> None:
        payload = {"conversation_id": conversation_id, **data}
        notify_user(notification_route_id, "agent_loop_finished", payload)

    logger.info(
        "conversation_agent_task started: conversation=%s user=%s agents=%s tools=%s modality=%s",
        conversation_id, user_id, agent_slugs, tool_names, multiagentic_modality,
    )

    agent_sessions_created = []
    try:
        # ---- Save or reuse user message ----
        if regenerate_message_id:
            try:
                user_message = Message.objects.get(
                    id=regenerate_message_id,
                    conversation=conversation,
                    type="user",
                )
                user_message.text = user_message_text
                user_message.attachments = message_attachments
                user_message.save(update_fields=["text", "attachments"])
                Message.objects.filter(
                    conversation=conversation,
                    id__gt=user_message.id,
                ).delete()
            except Message.DoesNotExist:
                emit_event("error", {"error": "Message to regenerate not found"})
                return {"status": "error", "error": "Message to regenerate not found"}
        else:
            try:
                user_message = Message.objects.create(
                    conversation=conversation,
                    type="user",
                    text=user_message_text,
                    attachments=message_attachments,
                )
                for att in attachment_objects:
                    att.message = user_message
                    att.save(update_fields=["message"])
            except Exception:
                emit_event("error", {"error": "Failed to save user message"})
                return {"status": "error", "error": "Failed to save user message"}

        # ---- Resolve agents in order ----
        agents_by_slug = {a.slug: a for a in Agent.objects.filter(slug__in=agent_slugs)}
        agents_ordered = [agents_by_slug[s] for s in agent_slugs if s in agents_by_slug]
        if not agents_ordered:
            emit_event("error", {"error": "No valid agents found"})
            return {"status": "error", "error": "No valid agents found"}

        versions = []
        total_iterations = 0
        total_tool_calls = 0
        assistant_message_attachments: list[dict] = []
        assistant_attachment_ids: list[str] = []

        prev_messages = _serialize_prev_messages(conversation, user_message.id)

        attachment_ids = [
            inp.get("attachment_id") or inp.get("id")
            for inp in resolved_inputs
            if inp.get("type") == "input_attachment"
        ]
        attachment_ids_instruction = ""
        if attachment_ids:
            attachment_ids_instruction = (
                "\n\nThe user has attached items. Read them with the read_attachment tool. "
                "Available attachment IDs: " + ", ".join(str(aid) for aid in attachment_ids if aid) + "\n"
                "When referencing attachments in markdown:\n"
                "- Use ![Alt text](attachment:<attachment_id>) ONLY for image attachments.\n"
                "- For documents/audio/other files, use [Label](attachment:<attachment_id>) instead.\n"
            )

        # Pre-compute context shared across all agent iterations
        from datetime import datetime
        from api.authenticate.models import UserProfile

        current_date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        user_profile_text = ""
        if actor_user_id:
            try:
                user_profile_text = UserProfile.objects.get(
                    user_id=actor_user_id
                ).get_as_text()
            except UserProfile.DoesNotExist:
                pass

        for index, agent in enumerate(agents_ordered):
            instructions = agent.format_prompt()
            llm = agent.llm
            model_slug = llm.slug if llm else (agent.model_slug or "gpt-5.2")

            instructions += f"\n\nYour name is: {agent.name}."
            instructions += f"\nThe current date and time is {current_date_time}."
            if user_profile_text:
                instructions += f"\n{user_profile_text}"

            if attachment_ids_instruction:
                instructions = instructions + attachment_ids_instruction

            # If the user enabled RAG/Web Search, they expect the agent to use it.
            if "rag_query" in (tool_names or []):
                instructions += (
                    "\n\nRAG is enabled for this conversation. "
                    "Before answering, you MUST call rag_query at least once with a small list of queries "
                    "(1-5) derived from the user's latest request. "
                    "If rag_query returns no results, say so briefly and continue with best-effort."
                )
            if "explore_web" in (tool_names or []):
                instructions += (
                    "\n\nWeb Search is enabled for this conversation. "
                    "Before answering, you MUST call explore_web at least once with an appropriate query "
                    "derived from the user's latest request. "
                    "Use the results to improve factuality; if it returns no results, say so briefly and continue."
                )
            if "create_image" in (tool_names or []):
                instructions += (
                    "\n\nImage generation is enabled for this conversation. "
                    "If the user asks you to generate an image, you can call create_image(prompt, model, aspect_ratio). "
                    "Use model='gpt-image-1.5'. aspect_ratio must be one of: square, landscape, portrait."
                    "\n\nWhen referencing an attachment inside your message markdown, prefer this format: "
                    "![Alt text](attachment:<attachment_id>). Do NOT invent /media/... URLs."
                )
            if "create_speech" in (tool_names or []):
                instructions += (
                    "\n\nSpeech generation is enabled (model: gpt-4o-mini-tts). "
                    "If the user asks for an audio version, call create_speech(text, voice, instructions, output_format). "
                    "voices: alloy, ash, ballad, coral, echo, fable, nova, onyx, sage, shimmer, verse, marin, cedar. "
                    "For best quality use marin or cedar. "
                    "The 'instructions' parameter lets you control accent, tone, speed, emotional range, whispering, etc. "
                    "Example: instructions='Speak slowly with a calm, soothing British accent.' "
                    "output_format must be mp3 or wav."
                    "\n\nWhen referencing the audio attachment in markdown, link it like: "
                    "[Listen](attachment:<attachment_id>)."
                )

            # For grupal: strong context about the group conversation
            if multiagentic_modality == "grupal":
                grupal_preamble = (
                    "\n\n=== GROUP CONVERSATION ===\n"
                    "You are participating in a GROUP CHAT alongside other AI assistants. "
                    "Each assistant takes turns responding to the same user message. "
                    "You can see the other assistants' responses in the conversation history — "
                    "they are real participants in this chat, not text pasted by the user. "
                    "Treat them as fellow participants: you can agree, disagree, add to, "
                    "or complement their responses. Do NOT repeat what they already said. "
                    "Give ONLY your own response — do not summarize or restate theirs.\n"
                    "=== END GROUP CONVERSATION ===\n"
                )
                if versions:
                    grupal_preamble += "\nResponses from other assistants so far:\n"
                    for v in versions:
                        grupal_preamble += f"\n--- {v.get('agent_name', 'Unknown')} ---\n{v.get('text', '')}\n"
                instructions = instructions + grupal_preamble

            # Available plugins summary (agent discovers and uses them on demand).
            instructions += format_available_plugins_summary()

            # ---- Create AgentSession (inputs) ----
            model_ref = ModelRef(
                id=llm.id if llm else 0,
                slug=model_slug,
                provider=llm.provider.name if llm else "openai",
            )
            inputs_data = AgentSessionInputs(
                instructions=instructions,
                user_inputs=resolved_inputs,
                user_message_text=user_message_text,
                tool_names=tool_names,
                plugin_slugs=[],
                agent=AgentRef(id=agent.id, slug=agent.slug, name=agent.name),
                model=model_ref,
                multiagentic_modality=multiagentic_modality,
                prev_messages=prev_messages,
                max_iterations=max_iterations,
            ).model_dump()

            session = AgentSession.objects.create(
                conversation=conversation,
                user_message=user_message,
                task_type="chat_message",
                inputs=inputs_data,
                outputs={},
                agent_index=index,
            )
            agent_sessions_created.append(session)
            start_time = time.perf_counter()

            def on_event(event_type: str, data: dict) -> None:
                payload = {
                    "type": event_type,
                    "conversation_id": conversation_id,
                    "agent_slug": agent.slug,
                    "agent_name": agent.name,
                    **data,
                }
                notify_user(notification_route_id, "agent_events_channel", payload)

            # Always include read_plugin_instructions so the agent can
            # discover plugin formatting rules on demand.
            if "read_plugin_instructions" not in tool_names:
                tool_names.append("read_plugin_instructions")

            tools = resolve_tools(
                tool_names,
                conversation_id=conversation_id,
                user_id=actor_user_id,
                agent_slug=agent.slug,
            )

            loop = AgentLoop(
                tools=tools,
                instructions=instructions,
                model=model_slug,
                max_iterations=max_iterations,
                on_event=on_event,
            )

            openai_inputs = _build_agent_loop_inputs(
                prev_messages=prev_messages,
                current_user_text=user_message_text,
                current_user_attachments=message_attachments,
                agent_slug=agent.slug,
                multiagentic_modality=multiagentic_modality,
            )
            result = loop.run(openai_inputs)

            # ---- Update AgentSession (outputs) ----
            from django.utils import timezone

            # ---- Collect any generated attachments (image/audio) ----
            new_atts, new_ids = _extract_create_image_attachments(result.tool_calls or [])
            if new_atts:
                assistant_message_attachments.extend(new_atts)
            if new_ids:
                assistant_attachment_ids.extend(new_ids)
 
            speech_atts, speech_ids = _extract_create_speech_attachments(result.tool_calls or [])
            if speech_atts:
                assistant_message_attachments.extend(speech_atts)
            if speech_ids:
                assistant_attachment_ids.extend(speech_ids)

            if isinstance(result.output, str):
                output_value = OutputValue(type="string", value=result.output)
            elif hasattr(result.output, "model_dump"):
                dump = result.output.model_dump(mode="json")
                output_value = OutputValue(type="json", value=dump)
            else:
                output_value = OutputValue(type="string", value=str(result.output))

            outputs_data = AgentSessionOutputs(
                messages=result.messages,
                output=output_value,
                usage=result.usage,
                status="completed",
                error=None,
            ).model_dump()

            session.outputs = outputs_data
            session.iterations = result.iterations
            session.tool_calls_count = len(result.tool_calls)
            session.ended_at = timezone.now()
            session.total_duration = time.perf_counter() - start_time
            session.save()

            # ---- Extract output text for version ----
            import json as _json
            if isinstance(result.output, str):
                output_text = result.output
            elif hasattr(result.output, "model_dump"):
                output_text = _json.dumps(result.output.model_dump(), default=str)
            else:
                output_text = str(result.output)

            # Also include attachments referenced in assistant markdown using
            # attachment:<uuid>, even when they were originally uploaded in
            # previous messages (e.g. user documents/images).
            referenced_atts = _extract_referenced_attachments_from_text(
                output_text,
                conversation_id=conversation_id,
            )
            if referenced_atts:
                existing_ids = {
                    str(a.get("attachment_id") or "")
                    for a in assistant_message_attachments
                }
                for att in referenced_atts:
                    aid = str(att.get("attachment_id") or "")
                    if aid and aid in existing_ids:
                        continue
                    assistant_message_attachments.append(att)
                    if aid:
                        existing_ids.add(aid)

            rag_sources = _extract_rag_sources(result.tool_calls or [])

            version = {
                "agent_slug": agent.slug,
                "agent_name": agent.name,
                "type": "assistant",
                "sources": rag_sources,
                "usage": {
                    "prompt_tokens": result.usage.get("prompt_tokens", 0),
                    "completion_tokens": result.usage.get("completion_tokens", 0),
                    "total_tokens": result.usage.get("total_tokens", 0),
                    "model_slug": model_slug,
                },
            }
            version["text"] = output_text
            versions.append(version)

            total_iterations += result.iterations
            total_tool_calls += len(result.tool_calls)

            # Emit version immediately so frontend can display it in real time
            emit_event("agent_version_ready", {"version": version})

            # Grupal: save a separate assistant message per agent (matches streaming behaviour)
            if multiagentic_modality == "grupal":
                try:
                    conv_ref = Conversation.objects.get(id=conversation_id)
                    grupal_msg = Message.objects.create(
                        conversation=conv_ref,
                        type="assistant",
                        text=output_text,
                        versions=[version],
                        attachments=assistant_message_attachments,
                    )
                    if assistant_attachment_ids:
                        from api.messaging.models import MessageAttachment
                        MessageAttachment.objects.filter(
                            conversation_id=conversation_id,
                            id__in=assistant_attachment_ids,
                        ).update(message=grupal_msg)
                    session.assistant_message = grupal_msg
                    session.save(update_fields=["assistant_message"])
                    # Reset per-agent attachment accumulators
                    assistant_message_attachments = []
                    assistant_attachment_ids = []

                    is_last_agent = index == len(agents_ordered) - 1
                    next_agent_slug = agents_ordered[index + 1].slug if not is_last_agent else None

                    emit_finished({
                        "output": output_text,
                        "message_id": grupal_msg.id,
                        "versions": [version],
                        "iterations": total_iterations,
                        "tool_calls_count": total_tool_calls,
                        "next_agent_slug": next_agent_slug,
                    })
                except Conversation.DoesNotExist:
                    logger.warning("Conversation %s not found (grupal save)", conversation_id)

            emit_event("agent_complete", {
                "agent_slug": agent.slug,
                "agent_name": agent.name,
                "index": index + 1,
                "total": len(agents_ordered),
            })

        # ---- Save assistant message (isolated: single message with all versions) ----
        if multiagentic_modality != "grupal":
            assistant_message_id = None
            primary_text = versions[0]["text"] if versions else ""
            try:
                conversation = Conversation.objects.get(id=conversation_id)
                assistant_msg = Message.objects.create(
                    conversation=conversation,
                    type="assistant",
                    text=primary_text,
                    versions=versions,
                    attachments=assistant_message_attachments,
                )
                assistant_message_id = assistant_msg.id
                if assistant_attachment_ids:
                    from api.messaging.models import MessageAttachment

                    MessageAttachment.objects.filter(
                        conversation_id=conversation_id,
                        id__in=assistant_attachment_ids,
                    ).update(message=assistant_msg)
                for s in agent_sessions_created:
                    s.assistant_message = assistant_msg
                    s.save(update_fields=["assistant_message"])
                conversation.generate_title()
            except Conversation.DoesNotExist:
                logger.warning(
                    "Conversation %s not found when saving assistant message",
                    conversation_id,
                )

            emit_finished({
                "output": primary_text,
                "message_id": assistant_message_id,
                "versions": versions,
                "iterations": total_iterations,
                "tool_calls_count": total_tool_calls,
            })

        if multiagentic_modality == "grupal":
            try:
                Conversation.objects.get(id=conversation_id).generate_title()
            except Conversation.DoesNotExist:
                pass

        logger.info(
            "conversation_agent_task completed: conversation=%s agents=%d iterations=%d tool_calls=%d",
            conversation_id, len(versions), total_iterations, total_tool_calls,
        )

        return {
            "status": "completed",
            "output": primary_text,
            "iterations": total_iterations,
            "tool_calls_count": total_tool_calls,
            "message_id": assistant_message_id,
        }

    except Exception as e:
        logger.error(
            "conversation_agent_task failed: conversation=%s error=%s",
            conversation_id, str(e),
        )
        emit_event("error", {"error": str(e)})

        # Update last created session with error outputs if any
        if agent_sessions_created:
            from django.utils import timezone

            last_session = agent_sessions_created[-1]
            outputs_data = AgentSessionOutputs(
                messages=last_session.outputs.get("messages", []),
                output=OutputValue(type="string", value=""),
                usage=last_session.outputs.get("usage", {}),
                status="error",
                error=OutputError(message=str(e), traceback=tb.format_exc()),
            ).model_dump()
            last_session.outputs = outputs_data
            last_session.ended_at = timezone.now()
            last_session.tool_calls_count = sum(
                1 for m in last_session.outputs.get("messages", [])
                if m.get("type") == "function_call"
            )
            if last_session.started_at:
                last_session.total_duration = (
                    timezone.now() - last_session.started_at
                ).total_seconds()
            last_session.save(
                update_fields=["outputs", "ended_at", "total_duration", "tool_calls_count"]
            )

        return {"status": "error", "error": str(e)}
