"""
Tool: change_conversation_summary

Updates Conversation.summary when the agent decides the stored summary is stale or missing.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.ai_layers.tools.change_conversation_tags import _conversation_in_organization
from api.messaging.models import Conversation

logger = logging.getLogger(__name__)

SUMMARY_MAX_LEN = 12000


class ChangeConversationSummaryParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(
        min_length=1,
        max_length=SUMMARY_MAX_LEN,
        description=(
            "Concise, useful summary of what this conversation is about (same language as the chat when possible). "
            "Typically one to four sentences."
        ),
    )

    @field_validator("summary")
    @classmethod
    def strip_summary(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("summary cannot be blank")
        return s[:SUMMARY_MAX_LEN]


class ChangeConversationSummaryResult(BaseModel):
    success: bool
    message: str


def _change_conversation_summary_impl(
    conversation_id: str,
    organization_id: int,
    summary: str,
) -> ChangeConversationSummaryResult:
    try:
        conversation = Conversation.objects.get(id=conversation_id)
    except Conversation.DoesNotExist:
        return ChangeConversationSummaryResult(
            success=False,
            message="Conversation not found.",
        )

    if not _conversation_in_organization(conversation, organization_id):
        return ChangeConversationSummaryResult(
            success=False,
            message="Conversation does not belong to this organization context.",
        )

    text = summary.strip()[:SUMMARY_MAX_LEN]
    if not text:
        return ChangeConversationSummaryResult(
            success=False,
            message="summary must be non-empty after trimming.",
        )

    conversation.summary = text
    conversation.save(update_fields=["summary", "updated_at"])
    logger.info(
        "change_conversation_summary: conversation=%s len=%s",
        conversation_id,
        len(text),
    )
    return ChangeConversationSummaryResult(
        success=True,
        message="Conversation summary updated.",
    )


def get_tool(
    conversation_id: str | None = None,
    organization_id: int | None = None,
    **kwargs,
) -> dict:
    if not conversation_id or organization_id is None:
        raise ValueError(
            "change_conversation_summary requires conversation_id and organization_id in context"
        )

    def change_conversation_summary(summary: str) -> ChangeConversationSummaryResult:
        return _change_conversation_summary_impl(
            conversation_id=conversation_id,
            organization_id=organization_id,
            summary=summary,
        )

    return {
        "name": "change_conversation_summary",
        "description": (
            "Replace the conversation’s stored summary with a concise, accurate description of the thread. "
            "Use sparingly: only when the summary is empty or the conversation’s main purpose has clearly changed."
        ),
        "parameters": ChangeConversationSummaryParams,
        "function": change_conversation_summary,
    }
