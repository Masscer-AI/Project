"""
Tool: query_conversation

Answers a focused question about another (or same) conversation owned by the user,
using a small inner LLM pass over a capped transcript — not full message dump to the main agent.
"""

from __future__ import annotations

import logging
import os
import re
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.messaging.models import Conversation, Message
from api.utils.openai_functions import create_structured_completion

logger = logging.getLogger(__name__)

# Bound inner context (main agent stays lean)
MAX_MESSAGES = 300
MAX_CHARS_PER_MESSAGE = 10_000
INNER_MODEL = os.environ.get("QUERY_CONVERSATION_MODEL", "gpt-4o-mini")
MAX_QUESTION_LEN = 2000


class QueryConversationParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: str = Field(
        min_length=36,
        max_length=36,
        description="UUID of the conversation to inspect (same user; often from get_tag_context).",
    )
    question: str = Field(
        min_length=1,
        max_length=MAX_QUESTION_LEN,
        description="What you need to know about that thread; be specific.",
    )

    @field_validator("conversation_id")
    @classmethod
    def validate_uuid(cls, v: str) -> str:
        s = v.strip().lower()
        try:
            uuid.UUID(s)
        except ValueError as exc:
            raise ValueError("conversation_id must be a valid UUID") from exc
        return s

    @field_validator("question")
    @classmethod
    def strip_question(cls, v: str) -> str:
        q = v.strip()
        if not q:
            raise ValueError("question cannot be blank")
        return q[:MAX_QUESTION_LEN]


class _InnerAnswer(BaseModel):
    """Structured output for the inner model."""

    answer: str = Field(
        description=(
            "Concise answer to the question using only the transcript. "
            "If the transcript does not contain the information, say so clearly in one or two sentences."
        )
    )


class QueryConversationResult(BaseModel):
    success: bool
    answer: str = Field(default="", description="Answer to the question (empty if failed)")
    message: str = Field(default="", description="Status or error hint for the main agent")


def _user_can_access_conversation(
    *,
    conv: Conversation,
    user_id: int,
    organization_id: int,
    has_organization_conversations_access: bool,
) -> bool:
    if conv.status == "deleted":
        return False
    if has_organization_conversations_access:
        from django.contrib.auth.models import User

        from api.messaging.views import _user_can_access_conversation as dashboard_can_access

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return False
        return dashboard_can_access(user, conv)

    if conv.user_id != user_id:
        return False
    oid = conv.organization_id
    if oid is None or oid == organization_id:
        return True
    return False


def _build_transcript(conv: Conversation) -> str:
    """Most recent messages first in DB slice, then chronological for the prompt."""
    qs = (
        Message.objects.filter(conversation=conv, type__in=("user", "assistant"))
        .order_by("-created_at")[:MAX_MESSAGES]
    )
    rows = list(qs)
    rows.reverse()
    lines: list[str] = []
    for m in rows:
        text = (m.text or "").strip()
        if len(text) > MAX_CHARS_PER_MESSAGE:
            text = text[:MAX_CHARS_PER_MESSAGE] + "\n… [truncated]"
        lines.append(f"{m.type}: {text}")
    return "\n".join(lines)


def _query_conversation_impl(
    *,
    target_conversation_id: str,
    question: str,
    organization_id: int,
    user_id: int | None = None,
    has_organization_conversations_access: bool = False,
    organization_scoped_embedded: bool = False,
) -> QueryConversationResult:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return QueryConversationResult(
            success=False,
            answer="",
            message="OpenAI API key is not configured.",
        )

    try:
        conv = Conversation.objects.get(id=target_conversation_id)
    except Conversation.DoesNotExist:
        return QueryConversationResult(
            success=False,
            answer="",
            message="Conversation not found.",
        )

    if organization_scoped_embedded:
        from api.ai_layers.tools.embedded_channels import organization_can_access_conversation

        if not organization_can_access_conversation(
            conv=conv,
            organization_id=organization_id,
        ):
            return QueryConversationResult(
                success=False,
                answer="",
                message=(
                    "You cannot access this conversation (wrong organization or deleted)."
                ),
            )
    elif user_id is None:
        return QueryConversationResult(
            success=False,
            answer="",
            message="query_conversation requires a logged-in user or organization context.",
        )
    elif not _user_can_access_conversation(
        conv=conv,
        user_id=user_id,
        organization_id=organization_id,
        has_organization_conversations_access=has_organization_conversations_access,
    ):
        return QueryConversationResult(
            success=False,
            answer="",
            message="You cannot access this conversation (wrong user, organization, or deleted).",
        )

    transcript = _build_transcript(conv)
    if not transcript.strip():
        return QueryConversationResult(
            success=True,
            answer="That conversation has no user/assistant messages to search.",
            message="Empty transcript.",
        )

    title = (conv.title or "").strip() or "(no title)"
    summary = (re.sub(r"\s+", " ", (conv.summary or "").strip())[:1500]) if conv.summary else ""

    system_prompt = """You are a precise assistant. You receive a CHAT TRANSCRIPT (user/assistant lines) from ONE past conversation and a QUESTION about it.

Rules:
- Answer ONLY from what appears in the transcript (and the short metadata lines). Do not invent messages or facts.
- Be concise (a few sentences unless the question truly needs more).
- Match the language of the QUESTION when reasonable.
- If the answer is not in the transcript, say clearly that the transcript does not show that information."""

    user_blob = (
        f"Conversation title: {title}\n"
        f"Stored summary (may be incomplete): {summary or '(none)'}\n\n"
        f"--- TRANSCRIPT (chronological) ---\n{transcript}\n--- END ---\n\n"
        f"QUESTION:\n{question}"
    )

    try:
        parsed = create_structured_completion(
            model=INNER_MODEL,
            system_prompt=system_prompt,
            user_prompt=user_blob,
            response_format=_InnerAnswer,
            api_key=api_key,
        )
        ans = (parsed.answer or "").strip()
        if not ans:
            ans = "No answer was produced."
        logger.info(
            "query_conversation: user=%s embedded_org=%s target=%s model=%s q_len=%s ans_len=%s org_wide=%s",
            user_id,
            organization_scoped_embedded,
            target_conversation_id,
            INNER_MODEL,
            len(question),
            len(ans),
            has_organization_conversations_access,
        )
        return QueryConversationResult(
            success=True,
            answer=ans,
            message=f"Answered using inner model {INNER_MODEL} over up to {MAX_MESSAGES} messages.",
        )
    except Exception as exc:
        logger.exception("query_conversation inner LLM failed: %s", exc)
        return QueryConversationResult(
            success=False,
            answer="",
            message=f"Inner analysis failed: {exc!s}",
        )


def get_tool(
    conversation_id: str | None = None,
    organization_id: int | None = None,
    user_id: int | None = None,
    has_organization_conversations_access: bool = False,
    is_whatsapp_visitor: bool = False,
    **kwargs,
) -> dict:
    if organization_id is None:
        raise ValueError("query_conversation requires organization_id in context")
    if is_whatsapp_visitor:
        def query_conversation(
            conversation_id: str,
            question: str,
        ) -> QueryConversationResult:
            return _query_conversation_impl(
                target_conversation_id=conversation_id.strip().lower(),
                question=question,
                organization_id=organization_id,
                organization_scoped_embedded=True,
            )

        return {
            "name": "query_conversation",
            "description": (
                "Ask a **specific question** about **one** conversation in this organization. "
                "Pass `conversation_id` (UUID from get_tag_context) and `question`. "
                "Returns a distilled answer from an inner model over that chat’s messages. "
                "Any org thread (WhatsApp, web, teammates) may be queried when you have its id."
            ),
            "parameters": QueryConversationParams,
            "function": query_conversation,
        }

    if user_id is None or not isinstance(user_id, int):
        raise ValueError("query_conversation requires a logged-in user_id in context")

    uid = int(user_id)
    wide = bool(has_organization_conversations_access)

    def query_conversation(
        conversation_id: str,
        question: str,
    ) -> QueryConversationResult:
        return _query_conversation_impl(
            target_conversation_id=conversation_id.strip().lower(),
            question=question,
            user_id=uid,
            organization_id=organization_id,
            has_organization_conversations_access=wide,
        )

    desc = (
        "Ask a **specific question** about **one** past conversation the user may access. "
        "Pass `conversation_id` (UUID, often from get_tag_context) and `question`. "
        "Returns only a distilled **answer** from an inner model over that chat’s messages (not full logs). "
    )
    if wide:
        desc += (
            "This session has **organization-wide** conversation access (same as the conversations dashboard): "
            "you may query teammates’ threads when policy allows. "
        )
    else:
        desc += "Only conversations **owned by this user** may be queried. "
    desc += (
        "Use for things like “what did we decide last week about X?” after you know which conversation_id to open. "
        "Requires logged-in user."
    )

    return {
        "name": "query_conversation",
        "description": desc,
        "parameters": QueryConversationParams,
        "function": query_conversation,
    }
