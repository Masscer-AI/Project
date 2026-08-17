"""
Tool: list_agents

Lists conversational agents the authenticated user can access, for handoff.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from api.ai_layers.access import accessible_agents_qs
from api.ai_layers.models import AgentKind


class ListAgentsParams(BaseModel):
    pass


class AgentSummary(BaseModel):
    slug: str
    name: str
    description: str = ""


class ListAgentsResult(BaseModel):
    agents: list[AgentSummary] = Field(default_factory=list)


def _list_agents_impl(
    *,
    user_id: int,
    current_agent_slug: str | None,
) -> ListAgentsResult:
    from django.contrib.auth.models import User

    user = User.objects.filter(pk=user_id).first()
    if not user:
        raise ValueError("User not found")

    qs = (
        accessible_agents_qs(user)
        .filter(agent_kind=AgentKind.CONVERSATIONAL_AGENT)
        .order_by("name")
    )
    if current_agent_slug:
        qs = qs.exclude(slug=current_agent_slug)

    agents = [
        AgentSummary(
            slug=agent.slug,
            name=agent.name,
            description=(agent.description or "").strip(),
        )
        for agent in qs
    ]
    return ListAgentsResult(agents=agents)


def get_tool(
    user_id: int | None = None,
    current_agent_slug: str | None = None,
    **kwargs,
) -> dict:
    if user_id is None:
        raise ValueError("list_agents requires user_id in tool context")

    def list_agents() -> ListAgentsResult:
        return _list_agents_impl(
            user_id=user_id,
            current_agent_slug=current_agent_slug,
        )

    return {
        "name": "list_agents",
        "description": (
            "List other conversational agents the user can access, with slug, name, "
            "and a short specialty description. Use before handoff_to_agent to pick "
            "the right specialist. Does not include you or platform assistants."
        ),
        "parameters": ListAgentsParams,
        "function": list_agents,
    }
