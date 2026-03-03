"""
Tool for listing attachments in a conversation.

Returns attachment IDs + metadata only (no file bytes, no document text).
Use read_attachment to read an attachment on demand.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ListAttachmentsParams(BaseModel):
    """Parameters for list_attachments tool (none for now)."""


class AttachmentListItem(BaseModel):
    attachment_id: str = Field(description="UUID of the attachment")
    kind: str = Field(description="Attachment kind: file|rag_document|website")
    content_type: str = Field(default="", description="MIME type (if known)")
    name: str | None = Field(default=None, description="Filename or document name (if available)")
    url: str | None = Field(default=None, description="Website URL (for kind=website)")
    message_id: int | None = Field(default=None, description="Message id this attachment is linked to (if any)")
    created_at: str | None = Field(default=None, description="Creation timestamp (ISO)")
    expires_at: str | None = Field(default=None, description="Expiry timestamp (ISO) or null")


class ListAttachmentsResult(BaseModel):
    attachments: list[AttachmentListItem] = Field(
        default_factory=list,
        description="All attachments in the conversation (metadata only)",
    )
    message: str = Field(default="Successfully listed attachments")


def _list_attachments_impl(conversation_id: str) -> ListAttachmentsResult:
    from api.messaging.models import MessageAttachment

    qs = (
        MessageAttachment.objects.filter(conversation_id=conversation_id)
        .select_related("rag_document", "message")
        .order_by("created_at")
    )

    items: list[AttachmentListItem] = []
    for att in qs:
        kind = getattr(att, "kind", "") or "file"
        name = None
        url = None

        if kind == "website":
            url = getattr(att, "url", None) or None
            name = url
        elif kind == "rag_document":
            doc = getattr(att, "rag_document", None)
            name = getattr(doc, "name", None) or (f"document_{getattr(doc, 'id', '')}" if doc else None)
        else:
            if att.file and getattr(att.file, "name", None):
                name = att.file.name.split("/")[-1]

        created_at = att.created_at.isoformat() if getattr(att, "created_at", None) else None
        expires_at = att.expires_at.isoformat() if getattr(att, "expires_at", None) else None

        items.append(
            AttachmentListItem(
                attachment_id=str(att.id),
                kind=kind,
                content_type=getattr(att, "content_type", "") or "",
                name=name,
                url=url,
                message_id=att.message_id,
                created_at=created_at,
                expires_at=expires_at,
            )
        )

    return ListAttachmentsResult(attachments=items)


def get_tool(
    conversation_id: str | None = None,
    **kwargs,
) -> dict:
    """
    Return an AgentTool dict for list_attachments.

    conversation_id is provided via closure by resolve_tools(..., conversation_id=...).
    """
    if not conversation_id:
        raise ValueError("list_attachments requires conversation_id in tool context")

    def list_attachments() -> ListAttachmentsResult:
        return _list_attachments_impl(conversation_id=conversation_id)

    return {
        "name": "list_attachments",
        "description": (
            "List all attachments available in the current conversation. "
            "Use this to discover attachment IDs, then call read_attachment(attachment_id, question) to read one."
        ),
        "parameters": ListAttachmentsParams,
        "function": list_attachments,
    }

