"""
Darwin-style WhatsApp inbound: idempotent user row + agent task with regenerate_message_id.
"""

from __future__ import annotations

import mimetypes
import uuid
from typing import Any

from django.core.files.base import ContentFile
from django.core.cache import cache

from api.messaging.models import Conversation, Message, MessageAttachment

from .media import fetch_whatsapp_media_bytes
from .models import WSNumber

_ALLOWED_IMAGE_MIMES = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/gif"}
)
WHATSAPP_INBOUND_DEBOUNCE_SECONDS = 3
WHATSAPP_INBOUND_BUFFER_TTL_SECONDS = 120

WHATSAPP_CLEAR_COMMAND = "/clear"
WHATSAPP_CLEAR_REPLY = "A new chat has started!"


def whatsapp_inbound_buffer_key(conversation_id: str) -> str:
    return f"whatsapp:inbound:buffer:{conversation_id}"


def whatsapp_inbound_schedule_lock_key(conversation_id: str) -> str:
    return f"whatsapp:inbound:flush_scheduled:{conversation_id}"


def is_clear_command(body: str) -> bool:
    return body.strip() == WHATSAPP_CLEAR_COMMAND


def clear_whatsapp_inbound_buffer(conversation_id: str) -> None:
    cache.delete(whatsapp_inbound_buffer_key(conversation_id))
    cache.delete(whatsapp_inbound_schedule_lock_key(conversation_id))


def handle_whatsapp_clear(
    *,
    ws_number: WSNumber,
    conversation: Conversation,
    user_phone: str,
    inbound_wamid: str,
) -> Conversation:
    """
    End the current active thread (inactive), start a new active one, reply on WhatsApp.
    Does not enqueue the agent.
    """
    from api.messaging.takeover import emit_message_created

    from .actions import send_message
    from .conversations import create_whatsapp_conversation

    if inbound_wamid_already_processed(conversation, inbound_wamid):
        from .conversations import get_active_whatsapp_conversation

        return get_active_whatsapp_conversation(ws_number, user_phone) or conversation

    clear_whatsapp_inbound_buffer(str(conversation.id))

    clear_msg = Message.objects.create(
        conversation=conversation,
        type="user",
        text=WHATSAPP_CLEAR_COMMAND,
        metadata={"whatsapp_inbound_wamid": inbound_wamid},
    )
    emit_message_created(None, conversation, clear_msg)

    conversation.status = "inactive"
    conversation.save(update_fields=["status", "updated_at"])

    new_conversation = create_whatsapp_conversation(ws_number, user_phone)

    out_wamid: str | None = None
    if ws_number.platform_id:
        out_wamid = send_message(
            ws_number.platform_id,
            user_phone,
            WHATSAPP_CLEAR_REPLY,
            inbound_wamid,
        )

    assistant_meta: dict[str, Any] = {}
    if out_wamid:
        assistant_meta["whatsapp_wamid"] = out_wamid
    assistant = Message.objects.create(
        conversation=new_conversation,
        type="assistant",
        text=WHATSAPP_CLEAR_REPLY,
        metadata=assistant_meta,
    )
    emit_message_created(None, new_conversation, assistant)

    new_conversation.whatsapp_last_inbound_wamid = inbound_wamid
    new_conversation.save(update_fields=["whatsapp_last_inbound_wamid", "updated_at"])

    return new_conversation


def inbound_wamid_already_processed(conversation: Conversation, wamid: str) -> bool:
    return Message.objects.filter(
        conversation=conversation,
        type="user",
        metadata__whatsapp_inbound_wamid=wamid,
    ).exists()


def _build_user_inputs_text(body: str) -> list[dict[str, Any]]:
    return [{"type": "input_text", "text": body}]


def _build_stub_message_text(user_inputs: list[dict[str, Any]]) -> str:
    """
    Best-effort text preview for the temporary inbound Message row.
    Used so realtime viewers don't see "." for normal text inbound while
    debounce/agent flush is still pending.
    """
    parts: list[str] = []
    for inp in user_inputs or []:
        if not isinstance(inp, dict):
            continue
        if inp.get("type") != "input_text":
            continue
        text = str(inp.get("text") or "").strip()
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def _build_user_inputs_image(
    conversation: Conversation,
    ws_number: WSNumber,
    *,
    media_id: str,
    media_url: str | None,
    caption: str,
) -> list[dict[str, Any]]:
    data, mime = fetch_whatsapp_media_bytes(media_id, direct_url=media_url)
    if mime not in _ALLOWED_IMAGE_MIMES:
        raise ValueError(f"Unsupported WhatsApp image mime type: {mime}")
    ext = mime.split("/")[-1] if "/" in mime else "jpg"
    fname = f"whatsapp-in-{uuid.uuid4().hex}.{ext}"
    att = MessageAttachment.objects.create(
        conversation=conversation,
        user=None,
        kind="file",
        content_type=mime,
        file=ContentFile(data, name=fname),
    )
    text = caption.strip() if caption.strip() else "See attached image(s)."
    return [
        {"type": "input_text", "text": text},
        {"type": "input_attachment", "attachment_id": str(att.id)},
    ]


def _build_user_inputs_document(
    conversation: Conversation,
    *,
    media_id: str,
    media_url: str | None,
    caption: str,
    filename: str | None,
) -> list[dict[str, Any]]:
    data, mime = fetch_whatsapp_media_bytes(media_id, direct_url=media_url)
    guessed_ext = mimetypes.guess_extension(mime or "") or ""
    ext = guessed_ext if guessed_ext else ".bin"
    fname = f"whatsapp-doc-{uuid.uuid4().hex}{ext}"
    att = MessageAttachment.objects.create(
        conversation=conversation,
        user=None,
        kind="file",
        content_type=mime,
        file=ContentFile(data, name=fname),
    )
    if caption.strip():
        text = caption.strip()
    elif filename:
        text = f"Please read attached document: {filename}"
    else:
        text = "Please read attached document."
    return [
        {"type": "input_text", "text": text},
        {"type": "input_attachment", "attachment_id": str(att.id)},
    ]


def enqueue_whatsapp_inbound_agent(
    *,
    conversation: Conversation,
    ws_number: WSNumber,
    whatsapp_user_number: str,
    inbound_wamid: str,
    user_inputs: list[dict[str, Any]],
) -> None:
    """Create placeholder user Message, buffer inbound payload, and schedule debounced flush."""
    from api.messaging.takeover import (
        emit_message_created,
        get_active_takeover,
        handle_inbound_during_takeover,
    )

    active_takeover = get_active_takeover(conversation)
    if active_takeover:
        handle_inbound_during_takeover(
            conversation,
            active_takeover,
            user_inputs,
            message_metadata={"whatsapp_inbound_wamid": inbound_wamid},
        )
        return

    from .tasks import whatsapp_flush_inbound_agent_task

    stub_text = _build_stub_message_text(user_inputs) or "."
    stub = Message.objects.create(
        conversation=conversation,
        type="user",
        text=stub_text,
        metadata={"whatsapp_inbound_wamid": inbound_wamid},
    )
    emit_message_created(None, conversation, stub)
    conversation_id = str(conversation.id)
    buffer_key = whatsapp_inbound_buffer_key(conversation_id)
    schedule_lock_key = whatsapp_inbound_schedule_lock_key(conversation_id)

    buffered_payloads = cache.get(buffer_key) or []
    buffered_payloads.append(
        {
            "inbound_wamid": inbound_wamid,
            "user_inputs": user_inputs,
            "regenerate_message_id": stub.id,
        }
    )
    cache.set(buffer_key, buffered_payloads, timeout=WHATSAPP_INBOUND_BUFFER_TTL_SECONDS)

    if cache.add(schedule_lock_key, True, timeout=WHATSAPP_INBOUND_BUFFER_TTL_SECONDS):
        whatsapp_flush_inbound_agent_task.apply_async(
            kwargs={
                "conversation_id": conversation_id,
                "ws_number_id": ws_number.id,
                "whatsapp_user_number": whatsapp_user_number,
            },
            countdown=WHATSAPP_INBOUND_DEBOUNCE_SECONDS,
        )


def process_text_inbound(
    *,
    ws_number: WSNumber,
    conversation: Conversation,
    user_phone: str,
    inbound_wamid: str,
    body: str,
) -> None:
    if not body.strip():
        return
    if inbound_wamid_already_processed(conversation, inbound_wamid):
        return
    if is_clear_command(body):
        handle_whatsapp_clear(
            ws_number=ws_number,
            conversation=conversation,
            user_phone=user_phone,
            inbound_wamid=inbound_wamid,
        )
        return
    user_inputs = _build_user_inputs_text(body.strip())
    enqueue_whatsapp_inbound_agent(
        conversation=conversation,
        ws_number=ws_number,
        whatsapp_user_number=user_phone,
        inbound_wamid=inbound_wamid,
        user_inputs=user_inputs,
    )


def process_image_inbound(
    *,
    ws_number: WSNumber,
    conversation: Conversation,
    user_phone: str,
    inbound_wamid: str,
    image: dict[str, Any],
) -> None:
    if inbound_wamid_already_processed(conversation, inbound_wamid):
        return
    media_id = image.get("id")
    if not media_id:
        return
    media_url = image.get("url") or image.get("link")
    caption = (image.get("caption") or "").strip()
    user_inputs = _build_user_inputs_image(
        conversation,
        ws_number,
        media_id=str(media_id),
        media_url=media_url if isinstance(media_url, str) else None,
        caption=caption,
    )
    enqueue_whatsapp_inbound_agent(
        conversation=conversation,
        ws_number=ws_number,
        whatsapp_user_number=user_phone,
        inbound_wamid=inbound_wamid,
        user_inputs=user_inputs,
    )


def process_document_inbound(
    *,
    ws_number: WSNumber,
    conversation: Conversation,
    user_phone: str,
    inbound_wamid: str,
    document: dict[str, Any],
) -> None:
    if inbound_wamid_already_processed(conversation, inbound_wamid):
        return
    media_id = document.get("id")
    if not media_id:
        return
    media_url = document.get("url") or document.get("link")
    caption = (document.get("caption") or "").strip()
    filename = document.get("filename")
    user_inputs = _build_user_inputs_document(
        conversation,
        media_id=str(media_id),
        media_url=media_url if isinstance(media_url, str) else None,
        caption=caption,
        filename=filename if isinstance(filename, str) else None,
    )
    enqueue_whatsapp_inbound_agent(
        conversation=conversation,
        ws_number=ws_number,
        whatsapp_user_number=user_phone,
        inbound_wamid=inbound_wamid,
        user_inputs=user_inputs,
    )
