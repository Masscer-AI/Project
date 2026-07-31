"""
Tool: list_conversations

Lists conversations the current actor may access (same user on web and linked WhatsApp).
v1: active conversations only.
"""

from __future__ import annotations

import logging
from datetime import datetime

from django.db.models import Count, DateTimeField
from django.db.models.functions import Coalesce
from pydantic import BaseModel, ConfigDict, Field

from api.messaging.conversation_access import (
    conversation_channel,
    user_accessible_conversations_q,
)
from api.messaging.models import Conversation

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 30
MAX_LIMIT = 50


class ListConversationsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(
        default=DEFAULT_LIMIT,
        ge=1,
        le=MAX_LIMIT,
        description=f"Max conversations to return (1–{MAX_LIMIT}; default {DEFAULT_LIMIT}).",
    )


class ListConversationsItem(BaseModel):
    conversation_id: str
    title: str = ""
    summary: str = ""
    n_messages: int = Field(ge=0)
    date: str = ""
    channel: str = Field(description="whatsapp | web | widget")
    is_current: bool = False


class ListConversationsResult(BaseModel):
    conversations: list[ListConversationsItem] = Field(default_factory=list)
    message: str = ""


def _iso(dt: datetime | None) -> str:
    if dt is None:
        return ""
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)


def _list_conversations_impl(
    *,
    user_id: int,
    organization_id: int,
    current_conversation_id: str,
    has_organization_conversations_access: bool = False,
    limit: int = DEFAULT_LIMIT,
) -> ListConversationsResult:
    limit = max(1, min(int(limit), MAX_LIMIT))
    current_id = str(current_conversation_id)

    qs = (
        Conversation.objects.filter(
            user_accessible_conversations_q(
                user_id=user_id,
                organization_id=organization_id,
                has_organization_conversations_access=has_organization_conversations_access,
            ),
            status="active",
        )
        .annotate(n_messages=Count("messages"))
        .annotate(
            sort_date=Coalesce(
                "last_message_at",
                "updated_at",
                output_field=DateTimeField(),
            )
        )
        .order_by("-sort_date")[:limit]
    )

    items: list[ListConversationsItem] = []
    for conv in qs:
        dt = getattr(conv, "sort_date", None) or conv.updated_at
        items.append(
            ListConversationsItem(
                conversation_id=str(conv.id),
                title=(conv.title or "").strip(),
                summary=(conv.summary or "").strip(),
                n_messages=int(getattr(conv, "n_messages", 0) or 0),
                date=_iso(dt),
                channel=conversation_channel(conv),
                is_current=str(conv.id) == current_id,
            )
        )

    scope = "org" if has_organization_conversations_access else "user"
    logger.info(
        "list_conversations: user=%s org=%s current=%s scope=%s rows=%s",
        user_id,
        organization_id,
        current_id,
        scope,
        len(items),
    )
    if has_organization_conversations_access:
        msg = (
            f"Found {len(items)} active conversation(s) across the organization "
            "(same visibility as the conversations dashboard)."
        )
    else:
        msg = (
            f"Found {len(items)} active conversation(s) for this user "
            "(app chats they own and WhatsApp threads linked to them)."
        )
    return ListConversationsResult(conversations=items, message=msg)


def get_tool(
    conversation_id: str | None = None,
    organization_id: int | None = None,
    user_id: int | None = None,
    has_organization_conversations_access: bool = False,
    is_whatsapp_visitor: bool = False,
    **kwargs,
) -> dict:
    if is_whatsapp_visitor:
        raise ValueError(
            "list_conversations is not available for unlinked WhatsApp visitors"
        )
    if not conversation_id or organization_id is None:
        raise ValueError(
            "list_conversations requires conversation_id and organization_id in context"
        )
    if user_id is None or not isinstance(user_id, int):
        raise ValueError("list_conversations requires a logged-in user_id in context")

    uid = int(user_id)
    cid = str(conversation_id)
    wide = bool(has_organization_conversations_access)

    def list_conversations(limit: int = DEFAULT_LIMIT) -> ListConversationsResult:
        return _list_conversations_impl(
            user_id=uid,
            organization_id=organization_id,
            current_conversation_id=cid,
            has_organization_conversations_access=wide,
            limit=limit,
        )

    desc = (
        "List **active** conversations this user can access: their app chats and WhatsApp "
        "threads linked to them (via verified contact). Returns conversation_id, title, "
        "summary, n_messages, date, channel (whatsapp/web/widget), and is_current. "
        "Use to find another thread for the same person, then call query_conversation with "
        "that conversation_id. Does not list inactive/archived threads. "
    )
    if wide:
        desc += "This session has organization-wide conversation visibility. "
    desc += "Prefer this over guessing conversation ids."

    return {
        "name": "list_conversations",
        "description": desc,
        "parameters": ListConversationsParams,
        "function": list_conversations,
    }
