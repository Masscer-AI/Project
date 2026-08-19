"""
Tool: handoff_to_agent

Transfer the current conversation to another accessible agent.

Does not enqueue the next agent itself — writes into a shared handoff_request
dict so conversation_agent_task can finish this session and start a new one.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.ai_layers.access import accessible_agents_qs
from api.ai_layers.models import AgentKind

AGENT_INSTRUCTIONS_MAX_LEN = 8000
MESSAGE_FOR_USER_MAX_LEN = 8000


class HandoffToAgentParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_slug: str = Field(
        min_length=1,
        description=(
            "Slug of the target agent from list_agents. Must be another "
            "conversational agent the user can access."
        ),
    )
    agent_instructions: str = Field(
        min_length=1,
        max_length=AGENT_INSTRUCTIONS_MAX_LEN,
        description=(
            "Instructions the next agent needs to follow (private; not shown in "
            "the chat thread). Include what you already did, what remains, and "
            "any constraints or context they need."
        ),
    )
    message_for_user: str = Field(
        min_length=1,
        max_length=MESSAGE_FOR_USER_MAX_LEN,
        description=(
            "Required user-visible assistant message for this turn. Shown in the "
            "conversation as your reply (e.g. that you are handing off and why)."
        ),
    )

    @field_validator("agent_slug")
    @classmethod
    def strip_slug(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("agent_slug cannot be blank")
        return s

    @field_validator("agent_instructions", "message_for_user")
    @classmethod
    def strip_text(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("cannot be blank")
        return s


class HandoffToAgentResult(BaseModel):
    success: bool
    message: str
    to_agent_slug: str | None = None
    to_agent_name: str | None = None


def _handoff_to_agent_impl(
    *,
    agent_slug: str,
    agent_instructions: str,
    message_for_user: str,
    user_id: int,
    current_agent_slug: str,
    handoff_request: dict[str, Any],
    is_embedded_channel: bool = False,
) -> HandoffToAgentResult:
    if is_embedded_channel:
        return HandoffToAgentResult(
            success=False,
            message="Handoff is not available on WhatsApp or chat widget conversations.",
        )

    if handoff_request.get("requested"):
        return HandoffToAgentResult(
            success=False,
            message="A handoff was already requested in this turn.",
        )

    target_slug = agent_slug.strip()
    if target_slug == current_agent_slug:
        return HandoffToAgentResult(
            success=False,
            message="Cannot hand off to yourself. Choose a different agent from list_agents.",
        )

    from django.contrib.auth.models import User

    user = User.objects.filter(pk=user_id).first()
    if not user:
        return HandoffToAgentResult(success=False, message="User not found.")

    target = (
        accessible_agents_qs(user)
        .filter(
            agent_kind=AgentKind.CONVERSATIONAL_AGENT,
            slug=target_slug,
        )
        .first()
    )
    if not target:
        return HandoffToAgentResult(
            success=False,
            message=(
                f"Agent '{target_slug}' was not found or is not accessible. "
                "Call list_agents and pick a valid slug."
            ),
        )

    handoff_request.clear()
    handoff_request.update(
        {
            "requested": True,
            "to_agent_slug": target.slug,
            "to_agent_name": target.name,
            "to_agent_id": target.id,
            "agent_instructions": agent_instructions.strip()[
                :AGENT_INSTRUCTIONS_MAX_LEN
            ],
            "message_for_user": message_for_user.strip()[:MESSAGE_FOR_USER_MAX_LEN],
            "from_agent_slug": current_agent_slug,
        }
    )

    return HandoffToAgentResult(
        success=True,
        message=(
            f"Handoff to {target.name} ({target.slug}) accepted. "
            "Stop further work; your message_for_user will be shown and the next "
            "agent will continue with agent_instructions."
        ),
        to_agent_slug=target.slug,
        to_agent_name=target.name,
    )


def get_tool(
    user_id: int | None = None,
    current_agent_slug: str | None = None,
    handoff_request: dict[str, Any] | None = None,
    is_whatsapp_chat: bool = False,
    chat_widget_id: int | str | None = None,
    **kwargs,
) -> dict:
    if user_id is None:
        raise ValueError("handoff_to_agent requires user_id in tool context")
    if not current_agent_slug:
        raise ValueError("handoff_to_agent requires current_agent_slug in tool context")
    if handoff_request is None:
        raise ValueError("handoff_to_agent requires handoff_request in tool context")

    is_embedded = bool(is_whatsapp_chat or chat_widget_id)

    def handoff_to_agent(
        agent_slug: str,
        agent_instructions: str,
        message_for_user: str,
    ) -> HandoffToAgentResult:
        return _handoff_to_agent_impl(
            agent_slug=agent_slug,
            agent_instructions=agent_instructions,
            message_for_user=message_for_user,
            user_id=user_id,
            current_agent_slug=current_agent_slug,
            handoff_request=handoff_request,
            is_embedded_channel=is_embedded,
        )

    return {
        "name": "handoff_to_agent",
        "description": (
            "Hand off this conversation to another specialist agent. "
            "Call list_agents first. Provide message_for_user (shown to the user as "
            "your assistant reply) and agent_instructions (private instructions the "
            "next agent must follow). "
            "After a successful handoff, do not continue working — stop."
        ),
        "parameters": HandoffToAgentParams,
        "function": handoff_to_agent,
    }
