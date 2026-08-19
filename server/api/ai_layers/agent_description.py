"""
Generate Agent.description for handoff / list_agents discovery.

Used by Django admin and the agent settings UI. LLM cost is registered against
the agent's organization wallet when present, otherwise the user's personal wallet.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DESCRIPTION_MODEL_SLUG = "gpt-5.6-luna"
_MAX_CONTEXT_CHARS = 2500


class _AgentDescriptionOut(BaseModel):
    description: str = Field(
        description=(
            "One or two short sentences describing what this agent specializes in. "
            "Plain language for other agents choosing who to hand work to. "
            "No system-prompt instructions, no tool lists, no marketing fluff."
        ),
    )


def _truncate(text: str | None, limit: int = _MAX_CONTEXT_CHARS) -> str:
    raw = (text or "").strip()
    if len(raw) <= limit:
        return raw
    return raw[: limit - 1].rstrip() + "…"


def _usage_from_response(response: Any) -> tuple[int, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0
    prompt = int(getattr(usage, "input_tokens", 0) or 0)
    completion = int(getattr(usage, "output_tokens", 0) or 0)
    return prompt, completion


def generate_agent_description(
    agent,
    *,
    billing_user_id: int,
    organization_id=None,
    model_slug: str = DESCRIPTION_MODEL_SLUG,
    name: str | None = None,
    act_as: str | None = None,
    system_prompt: str | None = None,
    salute: str | None = None,
) -> str:
    """
    Call the LLM to draft a short specialty description and bill the org/user.

    Optional name/act_as/system_prompt/salute override the persisted agent fields
    so the UI can regenerate from unsaved draft values.

    Raises ValueError on empty/invalid model output.
    """
    from api.consumption.actions import register_llm_interaction
    from api.utils.openai_functions import (
        _extract_json_from_text,
        _extract_output_text,
        _response_text_format_from_pydantic,
    )
    from openai import OpenAI
    import os

    agent_name = name if name is not None else agent.name
    agent_act_as = act_as if act_as is not None else agent.act_as
    agent_system = system_prompt if system_prompt is not None else agent.system_prompt
    agent_salute = salute if salute is not None else agent.salute

    instructions = (
        "You write short specialty descriptions for AI agents. "
        "Other agents read these to decide who should handle a task. "
        "Output must match the JSON schema. "
        "Keep the description under 240 characters. "
        "Prefer concrete domains (tax, legal, support, research) over vague claims."
    )
    user_prompt = (
        f"Agent name: {agent_name}\n"
        f"Slug: {agent.slug}\n"
        f"Role / act_as:\n{_truncate(agent_act_as)}\n\n"
        f"System prompt template (may include placeholders):\n"
        f"{_truncate(agent_system)}\n\n"
        f"Greeting/salute:\n{_truncate(agent_salute, 500)}\n"
    )

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    completion = client.responses.create(
        model=model_slug,
        instructions=instructions,
        input=user_prompt,
        text={"format": _response_text_format_from_pydantic(_AgentDescriptionOut)},
        max_output_tokens=800,
    )

    prompt_tokens, completion_tokens = _usage_from_response(completion)
    if prompt_tokens or completion_tokens:
        register_llm_interaction(
            billing_user_id,
            prompt_tokens,
            completion_tokens,
            model_slug,
            organization_id=organization_id,
        )
    else:
        logger.warning(
            "generate_agent_description: no usage on response agent=%s model=%s",
            getattr(agent, "slug", None),
            model_slug,
        )

    parsed = _AgentDescriptionOut.model_validate(
        _extract_json_from_text(_extract_output_text(completion))
    )
    description = (parsed.description or "").strip()
    if not description:
        raise ValueError("Model returned an empty description.")
    if len(description) > 500:
        description = description[:499].rstrip() + "…"
    return description


def regenerate_agent_description(
    agent,
    *,
    billing_user_id: int,
    name: str | None = None,
    act_as: str | None = None,
    system_prompt: str | None = None,
    salute: str | None = None,
    persist: bool = True,
) -> str:
    """Always generate a new description (overwrites). Optionally persist it."""
    organization_id = getattr(agent, "organization_id", None)
    description = generate_agent_description(
        agent,
        billing_user_id=int(billing_user_id),
        organization_id=organization_id,
        name=name,
        act_as=act_as,
        system_prompt=system_prompt,
        salute=salute,
    )
    if persist:
        agent.description = description
        agent.save(update_fields=["description"])
    return description


def fill_empty_agent_description(
    agent,
    *,
    billing_user_id: int | None = None,
) -> str | None:
    """
    If ``agent.description`` is blank, generate and save one.

    Returns the new description, or None when skipped (already filled).
    Admin path requires an organization so cost hits the org wallet.
    """
    if (getattr(agent, "description", None) or "").strip():
        return None

    org = getattr(agent, "organization", None)
    organization_id = getattr(agent, "organization_id", None)
    if organization_id is None or org is None:
        raise ValueError(
            f"Agent '{agent.slug}' has no organization; cannot bill description generation."
        )

    user_id = billing_user_id or getattr(agent, "user_id", None) or getattr(
        org, "owner_id", None
    )
    if not user_id:
        raise ValueError(
            f"Agent '{agent.slug}' has no billing user (agent.user / org.owner)."
        )

    return regenerate_agent_description(
        agent,
        billing_user_id=int(user_id),
    )
