"""
Tool: create_completion

Persists a finetuning Completion for the current agent (pending approval). The DB
fields are named ``prompt`` and ``answer`` for historical reasons:

- ``prompt`` = cue / when this row applies (retrieval hint, situation, topic).
- ``answer`` = payload / what to apply (reply text, facts to memorize, style, etc.).

Indexed into RAG only after approval in Knowledge base.
"""

from __future__ import annotations

import logging

from django.db.models import Q
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Reasonable bounds (DB is TextField; keep payloads sane for LLM tool calls)
PROMPT_ANSWER_MAX_LEN = 50_000


class CreateCompletionParams(BaseModel):
    prompt: str = Field(
        description=(
            "Cue / when this training row applies: situation, topic, user intent, or keywords "
            "that should match (retrieval hint). Does NOT need to be a literal user chat message."
        )
    )
    answer: str = Field(
        description=(
            "Payload to apply when the cue matches: preferred reply, facts to memorize, tone, "
            "required opening line, procedure, etc. Put the teachable substance here — not empty acknowledgements."
        )
    )


class CreateCompletionResult(BaseModel):
    completion_id: int = Field(description="Database id of the saved Completion.")
    approved: bool = Field(description="Always false until reviewed in Knowledge base.")
    message: str = Field(description="Short status for the model to relay to the user.")


def _create_completion_impl(
    *,
    prompt: str,
    answer: str,
    user_id: int,
    agent_slug: str,
    conversation_id: str,
) -> CreateCompletionResult:
    from django.contrib.auth.models import User

    from api.ai_layers.access import accessible_agents_qs
    from api.ai_layers.models import Agent
    from api.authenticate.services import FeatureFlagService
    from api.finetuning.models import Completion
    from api.messaging.models import Conversation

    prompt = (prompt or "").strip()
    answer = (answer or "").strip()
    if not prompt or not answer:
        raise ValueError("prompt and answer must be non-empty after trimming.")

    if len(prompt) > PROMPT_ANSWER_MAX_LEN or len(answer) > PROMPT_ANSWER_MAX_LEN:
        raise ValueError(
            f"prompt and answer must each be at most {PROMPT_ANSWER_MAX_LEN} characters."
        )

    try:
        conversation = Conversation.objects.select_related(
            "organization", "chat_widget", "user"
        ).get(id=conversation_id)
    except Conversation.DoesNotExist:
        raise ValueError("Conversation not found")

    if conversation.chat_widget_id is not None:
        raise ValueError("create_completion is not available for widget conversations.")

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        raise ValueError("User not found")

    enabled, _reason = FeatureFlagService.is_feature_enabled(
        "train-agents",
        organization=getattr(conversation, "organization", None),
        user=user,
    )
    if not enabled:
        raise ValueError("The train-agents feature is not enabled for this user or organization.")

    agent = (
        Agent.objects.filter(slug=agent_slug)
        .filter(Q(is_public=True) | Q(id__in=accessible_agents_qs(user).values_list("id", flat=True)))
        .first()
    )
    if not agent:
        raise ValueError("Agent not found or user is not allowed to access it.")

    completion = Completion.objects.create(
        prompt=prompt,
        answer=answer,
        agent=agent,
        approved=False,
    )
    logger.info(
        "create_completion: id=%s agent=%s user=%s conv=%s",
        completion.id,
        agent_slug,
        user_id,
        conversation_id,
    )

    return CreateCompletionResult(
        completion_id=completion.id,
        approved=False,
        message=(
            "Saved as a pending training row (cue + payload). Link the user to edit or approve it "
            f"using markdown: [Edit training example](completion:{completion.id})."
        ),
    )


def get_tool(
    conversation_id: str | None = None,
    user_id: int | None = None,
    agent_slug: str | None = None,
    **kwargs,
) -> dict:
    if not conversation_id:
        raise ValueError("create_completion requires conversation_id in tool context")
    if user_id is None:
        raise ValueError("create_completion requires user_id in tool context")
    if not agent_slug:
        raise ValueError("create_completion requires agent_slug in tool context")

    def create_completion(prompt: str, answer: str) -> CreateCompletionResult:
        return _create_completion_impl(
            prompt=prompt,
            answer=answer,
            user_id=int(user_id),
            agent_slug=agent_slug,
            conversation_id=conversation_id,
        )

    return {
        "name": "create_completion",
        "description": (
            "Save one training row for this agent (pending approval). "
            "prompt = cue for WHEN it applies (topic/situation/hint for retrieval); "
            "answer = WHAT to apply (reply text, memorized facts, style, fixed openings, procedures). "
            "The fields need not mimic a verbatim chat turn; answer should contain real substance, not only meta acknowledgements. "
            "Use when the user teaches or asks to persist knowledge. "
            "After success, include [Edit training example](completion:<completion_id>). "
            "Pending until approved in Knowledge base; then RAG may use it."
        ),
        "parameters": CreateCompletionParams,
        "function": create_completion,
    }
