"""
Darwin-style WhatsApp inbound: idempotent user row + agent task with regenerate_message_id.
"""

from __future__ import annotations

import mimetypes
import uuid
from typing import Any

from django.core.files.base import ContentFile

from api.messaging.models import Conversation, Message, MessageAttachment

from .media import fetch_whatsapp_media_bytes
from .models import WSNumber

_ALLOWED_IMAGE_MIMES = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/gif"}
)


def inbound_wamid_already_processed(conversation: Conversation, wamid: str) -> bool:
    return Message.objects.filter(
        conversation=conversation,
        type="user",
        metadata__whatsapp_inbound_wamid=wamid,
    ).exists()


def _build_user_inputs_text(body: str) -> list[dict[str, Any]]:
    return [{"type": "input_text", "text": body}]


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
    """Create placeholder user Message, then run agent task with regenerate_message_id."""
    from .tasks import whatsapp_conversation_agent_task

    stub = Message.objects.create(
        conversation=conversation,
        type="user",
        text=".",
        metadata={"whatsapp_inbound_wamid": inbound_wamid},
    )
    whatsapp_conversation_agent_task.delay(
        conversation_id=str(conversation.id),
        user_inputs=user_inputs,
        ws_number_id=ws_number.id,
        whatsapp_user_number=whatsapp_user_number,
        inbound_wamid=inbound_wamid,
        regenerate_message_id=stub.id,
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
