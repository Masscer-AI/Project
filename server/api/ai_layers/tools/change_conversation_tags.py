"""
Tool: change_conversation_tags

Replaces Conversation.tags with up to three enabled tag IDs for this organization.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.messaging.models import Conversation, Tag
from api.messaging.tasks import get_user_organization

logger = logging.getLogger(__name__)

MAX_TAGS = 3


class ChangeConversationTagsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tag_ids: list[int] = Field(
        default_factory=list,
        description=(
            f"Tag IDs to set on this conversation (0–{MAX_TAGS} items). "
            "Replaces the previous list entirely. Use only enabled tags from this organization."
        ),
    )

    @field_validator("tag_ids")
    @classmethod
    def dedupe_and_cap(cls, v: list[int]) -> list[int]:
        if not isinstance(v, list):
            raise ValueError("tag_ids must be a list of integers")
        seen: set[int] = set()
        out: list[int] = []
        for raw in v:
            try:
                tid = int(raw)
            except (TypeError, ValueError):
                continue
            if tid in seen:
                continue
            seen.add(tid)
            out.append(tid)
            if len(out) >= MAX_TAGS:
                break
        return out


class ChangeConversationTagsResult(BaseModel):
    success: bool
    message: str
    tag_ids: list[int] = Field(default_factory=list)


def _conversation_in_organization(conversation: Conversation, organization_id: int) -> bool:
    if conversation.organization_id == organization_id:
        return True
    if conversation.user_id:
        org = get_user_organization(conversation.user)
        if org and org.id == organization_id:
            return True
    cw = getattr(conversation, "chat_widget", None)
    agent = getattr(cw, "agent", None) if cw else None
    if agent and getattr(agent, "organization_id", None) == organization_id:
        return True
    ws = getattr(conversation, "ws_number", None)
    if ws and getattr(ws, "organization_id", None) == organization_id:
        return True
    return False


def _change_conversation_tags_impl(
    conversation_id: str,
    organization_id: int,
    tag_ids: list[int],
) -> ChangeConversationTagsResult:
    try:
        conversation = Conversation.objects.get(id=conversation_id)
    except Conversation.DoesNotExist:
        return ChangeConversationTagsResult(
            success=False,
            message="Conversation not found.",
        )

    if not _conversation_in_organization(conversation, organization_id):
        return ChangeConversationTagsResult(
            success=False,
            message="Conversation does not belong to this organization context.",
        )

    if not tag_ids:
        conversation.tags = []
        conversation.save(update_fields=["tags", "updated_at"])
        logger.info("change_conversation_tags: cleared tags for conversation=%s", conversation_id)
        return ChangeConversationTagsResult(
            success=True,
            message="Conversation tags cleared.",
            tag_ids=[],
        )

    valid = list(
        Tag.objects.filter(
            id__in=tag_ids,
            organization_id=organization_id,
            enabled=True,
        )
        .order_by("id")
        .values_list("id", flat=True)
    )
    # Preserve caller order but only for ids that exist
    id_set = set(valid)
    ordered = [tid for tid in tag_ids if tid in id_set][:MAX_TAGS]

    if len(ordered) < len(tag_ids):
        logger.warning(
            "change_conversation_tags: some ids invalid or wrong org conv=%s requested=%s applied=%s",
            conversation_id,
            tag_ids,
            ordered,
        )

    conversation.tags = ordered
    conversation.save(update_fields=["tags", "updated_at"])
    logger.info(
        "change_conversation_tags: conversation=%s tag_ids=%s",
        conversation_id,
        ordered,
    )
    return ChangeConversationTagsResult(
        success=True,
        message=f"Conversation tags set to {len(ordered)} tag(s).",
        tag_ids=ordered,
    )


def get_tool(
    conversation_id: str | None = None,
    organization_id: int | None = None,
    **kwargs,
) -> dict:
    if not conversation_id or organization_id is None:
        raise ValueError(
            "change_conversation_tags requires conversation_id and organization_id in context"
        )

    def change_conversation_tags(tag_ids: list[int] | None = None) -> ChangeConversationTagsResult:
        return _change_conversation_tags_impl(
            conversation_id=conversation_id,
            organization_id=organization_id,
            tag_ids=list(tag_ids or []),
        )

    return {
        "name": "change_conversation_tags",
        "description": (
            "Set this conversation's tags to exactly the given list of tag IDs (max 3). "
            "Replaces any previous tags. Pass an empty list to clear tags. "
            "Only use tag IDs from this organization (from query_organization_tags or create_organization_tag)."
        ),
        "parameters": ChangeConversationTagsParams,
        "function": change_conversation_tags,
    }
