"""Cross-conversation gallery of agent-generated MessageAttachment files."""

from __future__ import annotations

from django.db.models import Q, QuerySet

from api.messaging.attachment_urls import absolute_file_url_for_attachment
from api.messaging.models import Conversation, MessageAttachment

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
