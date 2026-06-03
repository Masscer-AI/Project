"""
Tool: get_tag_context

Returns other conversations that share a given tag id: by default only those
for the same user; when the actor has the conversations-dashboard feature,
organization-wide threads (same rules as the org conversation list).
"""

from __future__ import annotations

import logging
from datetime import datetime

from django.db.models import Count, DateTimeField, Q
from django.db.models.functions import Coalesce
from pydantic import BaseModel, ConfigDict, Field

from api.messaging.models import Conversation, Tag

logger = logging.getLogger(__name__)

MAX_CONVERSATIONS = 30


class GetTagContextParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tag_id: int = Field(
        ge=1,
        description=(
            "Numeric primary key of the tag (integer), e.g. 12 — NOT the tag title text. "
            "Use the tag_id shown next to current conversation tags or returned by query_organization_tags."
        ),
    )


class TagContextConversationItem(BaseModel):
    conversation_id: str = Field(description="UUID of the conversation")
    title: str = Field(default="", description="Conversation title if set")
    summary: str = Field(default="", description="Stored summary, may be empty")
    n_messages: int = Field(ge=0, description="Number of messages in the thread")
    date: str = Field(
        default="",
        description="ISO-8601 timestamp: last_message_at if set, otherwise updated_at",
    )


class GetTagContextResult(BaseModel):
    conversations: list[TagContextConversationItem] = Field(default_factory=list)
    message: str = Field(default="")


def _iso(dt: datetime | None) -> str:
    if dt is None:
        return ""
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)


def _get_tag_context_impl(
    *,
    tag_id: int,
    user_id: int,
    organization_id: int,
    current_conversation_id: str,
    has_organization_conversations_access: bool = False,
) -> GetTagContextResult:
    tag = (
        Tag.objects.filter(
            id=tag_id,
            organization_id=organization_id,
            enabled=True,
        )
        .only("id", "title")
        .first()
    )
    if not tag:
        return GetTagContextResult(
            conversations=[],
            message="Tag not found, not in this organization, or disabled.",
        )

    if has_organization_conversations_access:
        from django.contrib.auth.models import User

        from api.messaging.views import _get_org_user_ids

        try:
            actor = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return GetTagContextResult(
                conversations=[],
                message="User not found for tag context.",
            )
        org_user_ids = _get_org_user_ids(actor)
        if org_user_ids:
            base = Conversation.objects.filter(
                Q(user_id__in=org_user_ids)
                | Q(
                    user__isnull=True,
                    chat_widget__created_by_id__in=org_user_ids,
                )
            )
        else:
            base = Conversation.objects.filter(user_id=user_id)
    else:
        base = (
            Conversation.objects.filter(user_id=user_id)
            .filter(
                Q(organization_id=organization_id) | Q(organization_id__isnull=True)
            )
        )

    qs = (
        base.filter(tags__contains=[tag_id])
        .exclude(status="deleted")
        .exclude(id=current_conversation_id)
        .annotate(n_messages=Count("messages"))
        .annotate(
            sort_date=Coalesce(
                "last_message_at",
                "updated_at",
                output_field=DateTimeField(),
            )
        )
        .order_by("-sort_date")[:MAX_CONVERSATIONS]
    )

    items: list[TagContextConversationItem] = []
    for conv in qs:
        dt = getattr(conv, "sort_date", None) or conv.updated_at
        items.append(
            TagContextConversationItem(
                conversation_id=str(conv.id),
                title=(conv.title or "").strip(),
                summary=(conv.summary or "").strip(),
                n_messages=int(getattr(conv, "n_messages", 0) or 0),
                date=_iso(dt),
            )
        )

    scope = "org" if has_organization_conversations_access else "user"
    logger.info(
        "get_tag_context: user=%s tag_id=%s org=%s current=%s scope=%s rows=%s",
        user_id,
        tag_id,
        organization_id,
        current_conversation_id,
        scope,
        len(items),
    )
    if has_organization_conversations_access:
        msg = (
            f"Found {len(items)} other conversation(s) across the organization with tag "
            f"{tag_id!r} ({tag.title!r})."
        )
    else:
        msg = (
            f"Found {len(items)} other conversation(s) for this user with tag "
            f"{tag_id!r} ({tag.title!r})."
        )
    return GetTagContextResult(conversations=items, message=msg)


def _get_tag_context_organization_impl(
    *,
    tag_id: int,
    organization_id,
    current_conversation_id: str,
) -> GetTagContextResult:
    """All org threads with a tag (same visibility as dashboard scope=org)."""
    from api.messaging.views import organization_conversations_q

    tag = (
        Tag.objects.filter(
            id=tag_id,
            organization_id=organization_id,
            enabled=True,
        )
        .only("id", "title")
        .first()
    )
    if not tag:
        return GetTagContextResult(
            conversations=[],
            message="Tag not found, not in this organization, or disabled.",
        )

    tag_match = Q(tags__contains=[tag_id]) | Q(tags__contains=[str(tag_id)])

    qs = (
        Conversation.objects.filter(organization_conversations_q(organization_id))
        .filter(tag_match)
        .exclude(status="deleted")
        .exclude(id=current_conversation_id)
        .annotate(n_messages=Count("messages"))
        .annotate(
            sort_date=Coalesce(
                "last_message_at",
                "updated_at",
                output_field=DateTimeField(),
            )
        )
        .order_by("-sort_date")[:MAX_CONVERSATIONS]
    )

    items: list[TagContextConversationItem] = []
    for conv in qs:
        dt = getattr(conv, "sort_date", None) or conv.updated_at
        items.append(
            TagContextConversationItem(
                conversation_id=str(conv.id),
                title=(conv.title or "").strip(),
                summary=(conv.summary or "").strip(),
                n_messages=int(getattr(conv, "n_messages", 0) or 0),
                date=_iso(dt),
            )
        )

    msg = (
        f"Found {len(items)} other conversation(s) across the organization with tag "
        f"{tag_id!r} ({tag.title!r})."
    )
    logger.info(
        "get_tag_context: org=%s tag_id=%s current=%s scope=org_embedded rows=%s",
        organization_id,
        tag_id,
        current_conversation_id,
        len(items),
    )
    return GetTagContextResult(conversations=items, message=msg)


def get_tool(
    conversation_id: str | None = None,
    organization_id: int | None = None,
    user_id: int | None = None,
    has_organization_conversations_access: bool = False,
    is_whatsapp_visitor: bool = False,
    **kwargs,
) -> dict:
    if not conversation_id or organization_id is None:
        raise ValueError(
            "get_tag_context requires conversation_id and organization_id in context"
        )
    cid = str(conversation_id)

    if is_whatsapp_visitor:
        def get_tag_context(tag_id: int) -> GetTagContextResult:
            return _get_tag_context_organization_impl(
                tag_id=tag_id,
                organization_id=organization_id,
                current_conversation_id=cid,
            )

        return {
            "name": "get_tag_context",
            "description": (
                "Fetch cross-thread context for ONE tag in this organization: pass tag_id as an INTEGER. "
                "Returns other conversations with that tag **across the organization** "
                "(WhatsApp, web, teammates; title, summary, n_messages, date). "
                "Call before reusing a topic when a tag applies."
            ),
            "parameters": GetTagContextParams,
            "function": get_tag_context,
        }

    if user_id is None or not isinstance(user_id, int):
        raise ValueError("get_tag_context requires a logged-in user_id in context")

    uid = int(user_id)
    wide = bool(has_organization_conversations_access)

    def get_tag_context(tag_id: int) -> GetTagContextResult:
        return _get_tag_context_impl(
            tag_id=tag_id,
            user_id=uid,
            organization_id=organization_id,
            current_conversation_id=cid,
            has_organization_conversations_access=wide,
        )

    desc = (
        "Fetch cross-thread context for ONE tag: pass tag_id as an INTEGER (the tag’s database id), "
        "e.g. tag_id=7 — never pass the tag title string. Returns other conversations that already have that tag "
        "(title, summary, n_messages, date; current chat excluded). "
    )
    if wide:
        desc += (
            "This user has **organization-wide** conversation access: results include teammates’ threads in the org, "
            "not only their own. "
        )
    else:
        desc += "For this user, results are **only their own** other threads with that tag. "
    desc += (
        "Call when the user is working on a topic that matches a tag you are considering or already assigned "
        "(same app, client, project, product line) so you can align with prior threads; skip for unrelated chit-chat. "
        "If the list is empty, continue without inventing past chats."
    )

    return {
        "name": "get_tag_context",
        "description": desc,
        "parameters": GetTagContextParams,
        "function": get_tag_context,
    }
