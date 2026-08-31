"""
Tool for listing a user's message attachments.

Authenticated users: all of their attachments across conversations.
Anonymous sessions (widget / unlinked WhatsApp): current conversation only.

Returns attachment IDs + metadata only (no file bytes, no document text).
Use read_attachment to read an attachment on demand.
"""

from __future__ import annotations

from datetime import datetime, time
from typing import Literal

from django.db.models import Q
from django.utils import timezone
from pydantic import BaseModel, Field

from api.ai_layers.tools.attachment_access import (
    attachment_belongs_to_payload,
    attachments_visible_q,
)
from api.messaging.gallery import gallery_display_type

AttachmentMediaKind = Literal["image", "document", "video", "audio"]

MAX_LIMIT = 50


class ListAttachmentsParams(BaseModel):
    kind: AttachmentMediaKind = Field(
        description="Media type to list: image, document, video, or audio.",
    )
    from_date: str | None = Field(
        default=None,
        description=(
            "Optional ISO date (YYYY-MM-DD) or datetime. "
            "When set, only attachments created on or after this instant are returned."
        ),
    )


class AttachmentListItem(BaseModel):
    attachment_id: str = Field(description="UUID of the attachment")
    kind: str = Field(description="Media type: image|document|video|audio")
    attachment_kind: str = Field(
        description="Storage kind: file|rag_document|website",
    )
    content_type: str = Field(default="", description="MIME type (if known)")
    name: str | None = Field(
        default=None, description="Filename or document name (if available)"
    )
    url: str | None = Field(
        default=None, description="Website URL (for attachment_kind=website)"
    )
    conversation_id: str | None = Field(
        default=None, description="Conversation this attachment belongs to"
    )
    message_id: int | None = Field(
        default=None,
        description="Message id this attachment is linked to (if any)",
    )
    created_at: str | None = Field(default=None, description="Creation timestamp (ISO)")
    expires_at: str | None = Field(
        default=None, description="Expiry timestamp (ISO) or null"
    )
    is_current: bool = Field(
        default=False,
        description="True when the attachment belongs to the current conversation",
    )
    visibility: str = Field(
        default="personal",
        description="Access: personal, organization, roles, or link",
    )
    belongs_to: dict = Field(
        default_factory=dict,
        description="Ownership summary (you / organization / roles / link)",
    )


class ListAttachmentsResult(BaseModel):
    attachments: list[AttachmentListItem] = Field(
        default_factory=list,
        description="Matching attachments (metadata only)",
    )
    message: str = Field(default="Successfully listed attachments")


def _parse_from_date(value: str) -> datetime:
    raw = (value or "").strip()
    if not raw:
        raise ValueError("from_date cannot be blank")
    try:
        if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
            day = datetime.strptime(raw, "%Y-%m-%d").date()
            dt = datetime.combine(day, time.min)
        else:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            "from_date must be YYYY-MM-DD or an ISO datetime (e.g. 2026-08-01 or 2026-08-01T12:00:00Z)"
        ) from exc
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _media_type_filter(kind: AttachmentMediaKind) -> Q:
    from api.messaging.gallery import _type_filter

    return _type_filter(kind)


def _coerce_org_id(organization_id) -> int | None:
    if organization_id is None or organization_id == "":
        return None
    try:
        return int(organization_id)
    except (TypeError, ValueError):
        return None


def _attachment_name(att) -> tuple[str | None, str | None]:
    kind = getattr(att, "kind", "") or "file"
    name = None
    url = None
    if kind == "website":
        url = getattr(att, "url", None) or None
        name = url
    elif kind == "rag_document":
        doc = getattr(att, "rag_document", None)
        name = getattr(doc, "name", None) or (
            f"document_{getattr(doc, 'id', '')}" if doc else None
        )
    elif att.file and getattr(att.file, "name", None):
        name = att.file.name.split("/")[-1]
    return name, url


def _list_attachments_impl(
    *,
    kind: AttachmentMediaKind,
    from_date: str | None = None,
    user_id: int | None = None,
    conversation_id: str | None = None,
    organization_id: int | None = None,
    include_compliance_evidence: bool = False,
) -> ListAttachmentsResult:
    from django.contrib.auth.models import User

    from api.messaging.models import MessageAttachment

    actor = None
    if user_id is not None:
        actor = User.objects.filter(pk=int(user_id)).first()

    qs = (
        MessageAttachment.objects.filter(
            attachments_visible_q(
                user_id=user_id,
                conversation_id=conversation_id,
                organization_id=organization_id,
                include_compliance_evidence=include_compliance_evidence,
            )
        )
        .filter(_media_type_filter(kind))
        .select_related("rag_document", "message", "conversation", "organization", "user")
        .prefetch_related("allowed_roles")
        .distinct()
        .order_by("-created_at")
    )

    if kind in ("image", "video", "audio"):
        qs = qs.filter(kind="file").exclude(file__isnull=True).exclude(file="")

    now = timezone.now()
    qs = qs.filter(Q(expires_at__isnull=True) | Q(expires_at__gte=now))

    if from_date:
        qs = qs.filter(created_at__gte=_parse_from_date(from_date))

    total = qs.count()
    rows = list(qs[:MAX_LIMIT])
    current_id = str(conversation_id) if conversation_id else None

    items: list[AttachmentListItem] = []
    for att in rows:
        name, url = _attachment_name(att)
        created_at = att.created_at.isoformat() if getattr(att, "created_at", None) else None
        expires_at = att.expires_at.isoformat() if getattr(att, "expires_at", None) else None
        conv_id = str(att.conversation_id) if att.conversation_id else None
        items.append(
            AttachmentListItem(
                attachment_id=str(att.id),
                kind=gallery_display_type(att.content_type or ""),
                attachment_kind=getattr(att, "kind", "") or "file",
                content_type=getattr(att, "content_type", "") or "",
                name=name,
                url=url,
                conversation_id=conv_id,
                message_id=att.message_id,
                created_at=created_at,
                expires_at=expires_at,
                is_current=bool(current_id and conv_id == current_id),
                visibility=getattr(att, "visibility", None) or "personal",
                belongs_to=attachment_belongs_to_payload(att, actor),
            )
        )

    shown = len(items)
    scope = (
        "this user's conversations"
        if user_id is not None
        else "the current conversation"
    )
    message = f"Listed {shown} {kind} attachment(s) across {scope}."
    if total > shown:
        message += f" Showing the {shown} most recent of {total}."
    if from_date:
        message += f" Filtered from_date={from_date.strip()}."

    return ListAttachmentsResult(attachments=items, message=message)


def get_tool(
    conversation_id: str | None = None,
    user_id: int | None = None,
    organization_id: int | str | None = None,
    include_compliance_evidence: bool = False,
    **kwargs,
) -> dict:
    """
    Return an AgentTool dict for list_attachments.

    user_id / conversation_id / organization_id are provided via closure by
    resolve_tools(...).
    """
    if user_id is None and not conversation_id:
        raise ValueError(
            "list_attachments requires user_id or conversation_id in tool context"
        )

    org_id = _coerce_org_id(organization_id)

    def list_attachments(
        kind: AttachmentMediaKind,
        from_date: str | None = None,
    ) -> ListAttachmentsResult:
        return _list_attachments_impl(
            kind=kind,
            from_date=from_date,
            user_id=user_id,
            conversation_id=conversation_id,
            organization_id=org_id,
            include_compliance_evidence=include_compliance_evidence,
        )

    if user_id is not None:
        description = (
            "List attachments this user can access: their personal files, "
            "organization- and role-shared files, and public (link) files in their org, "
            "plus anything in the current conversation. "
            "kind is required: image, document, video, or audio. "
            "Optionally pass from_date (YYYY-MM-DD or ISO datetime) to only include "
            "attachments created since that instant. "
            "Returns attachment IDs and metadata; then call "
            "read_attachment(attachment_id, question) to read one. "
            "To send a listed file on WhatsApp, include "
            "[Download name](attachment:<attachment_id>) in the reply. "
            "Use update_attachment_visibility after generating a file if other "
            "org members need to list or receive it."
        )
    else:
        description = (
            "List attachments available in the current conversation. "
            "kind is required: image, document, video, or audio. "
            "Optionally pass from_date (YYYY-MM-DD or ISO datetime) to only include "
            "attachments created since that instant. "
            "Use this to discover attachment IDs, then call "
            "read_attachment(attachment_id, question) to read one."
        )

    return {
        "name": "list_attachments",
        "description": description,
        "parameters": ListAttachmentsParams,
        "function": list_attachments,
    }
