"""Cross-conversation gallery of agent-generated MessageAttachment files."""

from __future__ import annotations

import logging
import re

from django.db import transaction
from django.db.models import Q, QuerySet

from api.messaging.attachment_urls import absolute_file_url_for_attachment
from api.messaging.models import Conversation, Message, MessageAttachment

logger = logging.getLogger(__name__)

GALLERY_TYPES = ("image", "video", "audio", "document")


def _accessible_conversations_qs(user) -> QuerySet[Conversation]:
    """Personal chats the user owns, excluding soft-deleted."""
    return Conversation.objects.filter(user=user).exclude(status="deleted")


def _generations_q() -> Q:
    """Prefer agent-generated rows; metadata keys catch rare agent=None saves."""
    return (
        Q(agent_id__isnull=False)
        | Q(metadata__has_key="prompt")
        | Q(metadata__has_key="source")
        | Q(metadata__has_key="model")
    )


def _type_filter(gallery_type: str) -> Q:
    if gallery_type == "image":
        return Q(content_type__startswith="image/")
    if gallery_type == "video":
        return Q(content_type__startswith="video/")
    if gallery_type == "audio":
        return Q(content_type__startswith="audio/")
    # document: everything that is a file but not media
    return (
        ~Q(content_type__startswith="image/")
        & ~Q(content_type__startswith="video/")
        & ~Q(content_type__startswith="audio/")
    )


def gallery_display_type(content_type: str) -> str:
    ctype = content_type or ""
    if ctype.startswith("image/"):
        return "image"
    if ctype.startswith("video/"):
        return "video"
    if ctype.startswith("audio/"):
        return "audio"
    return "document"


def serialize_gallery_item(att: MessageAttachment) -> dict | None:
    url = absolute_file_url_for_attachment(att)
    if not url:
        return None

    file_field = att.file
    name = (
        file_field.name.split("/")[-1]
        if getattr(file_field, "name", None)
        else "file"
    )
    metadata = att.metadata if isinstance(att.metadata, dict) else {}
    prompt = metadata.get("prompt") or metadata.get("text") or None
    conversation = att.conversation

    return {
        "id": str(att.id),
        "url": url,
        "content_type": att.content_type or "",
        "type": gallery_display_type(att.content_type or ""),
        "name": name,
        "prompt": prompt,
        "metadata": metadata,
        "conversation_id": str(att.conversation_id),
        "conversation_title": (conversation.title if conversation else None) or "",
        "message_id": att.message_id,
        "created_at": att.created_at.isoformat() if att.created_at else None,
    }


def list_gallery_items(
    *,
    user,
    gallery_type: str = "image",
    limit: int = 48,
    offset: int = 0,
) -> dict:
    if gallery_type not in GALLERY_TYPES:
        gallery_type = "image"

    limit = min(max(1, limit), 100)
    offset = max(0, offset)

    conversations = _accessible_conversations_qs(user)
    qs = (
        MessageAttachment.objects.filter(
            kind="file",
            conversation__in=conversations,
        )
        .exclude(file__isnull=True)
        .exclude(file="")
        .filter(_generations_q())
        .filter(_type_filter(gallery_type))
        .select_related("conversation")
        .order_by("-created_at")
    )

    total = qs.count()
    page = list(qs[offset : offset + limit])
    results = []
    for att in page:
        item = serialize_gallery_item(att)
        if item:
            results.append(item)

    return {
        "results": results,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_next": offset + limit < total,
        "type": gallery_type,
    }


def _attachment_ref_matches(entry: dict, attachment_id: str, file_url: str | None) -> bool:
    aid = str(entry.get("attachment_id") or entry.get("id") or "")
    if aid and aid == attachment_id:
        return True
    if not file_url:
        return False
    content = entry.get("content") or ""
    if not content or not isinstance(content, str):
        return False
    if content == file_url:
        return True
    filename = file_url.split("?")[0].rstrip("/").split("/")[-1]
    if filename and filename in content:
        return True
    return False


def _scrub_attachment_from_message(
    message: Message,
    *,
    attachment_id: str,
    file_url: str | None,
) -> None:
    update_fields: list[str] = []
    attachments = list(message.attachments or [])
    filtered = [
        a
        for a in attachments
        if not (
            isinstance(a, dict)
            and _attachment_ref_matches(a, attachment_id, file_url)
        )
    ]
    if len(filtered) != len(attachments):
        message.attachments = filtered
        update_fields.append("attachments")

    text = message.text or ""
    if attachment_id and attachment_id in text:
        pattern = re.compile(
            rf"\[([^\]]*)\]\(attachment:{re.escape(attachment_id)}\)|"
            rf"attachment:{re.escape(attachment_id)}",
            re.IGNORECASE,
        )
        cleaned = pattern.sub("", text)
        cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        if cleaned != text:
            message.text = cleaned
            update_fields.append("text")

    if update_fields:
        message.save(update_fields=update_fields)


def _delete_attachment_file(attachment: MessageAttachment) -> None:
    if attachment.file:
        try:
            attachment.file.delete(save=False)
        except Exception:
            logger.exception("Failed to delete gallery attachment file %s", attachment.id)


def delete_gallery_attachment(*, user, attachment_id) -> dict:
    """
    Delete a gallery attachment the user owns: storage file, MessageAttachment row,
    and references on the linked Message (attachments JSON + markdown refs).
    """
    conversations = _accessible_conversations_qs(user)
    try:
        att = (
            MessageAttachment.objects.select_related("message", "conversation")
            .filter(conversation__in=conversations)
            .get(id=attachment_id)
        )
    except MessageAttachment.DoesNotExist:
        return {"ok": False, "error": "not_found"}

    attachment_id_str = str(att.id)
    file_url = absolute_file_url_for_attachment(att)

    with transaction.atomic():
        message = att.message
        if message is not None:
            _scrub_attachment_from_message(
                message,
                attachment_id=attachment_id_str,
                file_url=file_url,
            )
        else:
            for msg in Message.objects.filter(conversation_id=att.conversation_id):
                atts = msg.attachments or []
                if any(
                    isinstance(a, dict)
                    and _attachment_ref_matches(a, attachment_id_str, file_url)
                    for a in atts
                ):
                    _scrub_attachment_from_message(
                        msg,
                        attachment_id=attachment_id_str,
                        file_url=file_url,
                    )

        _delete_attachment_file(att)
        att.delete()

    return {"ok": True, "id": attachment_id_str}
