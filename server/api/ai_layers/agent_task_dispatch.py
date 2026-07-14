"""
Shared dispatch logic for conversation agent tasks.

Used by AgentTaskView and MCP gateway endpoints to avoid drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.core.cache import cache
from django.http import JsonResponse

from api.ai_layers.access import accessible_agents_qs, get_user_organization
from api.ai_layers.models import Agent, AgentKind
from api.ai_layers.agent_task_helpers import (
    parse_client_datetime as _parse_client_datetime,
    parse_regenerate_message_id as _parse_regenerate_message_id,
    validate_conversation_access as _validate_conversation_access,
)
from api.authenticate.services import FeatureFlagService
from api.messaging.models import Conversation
from api.messaging.schemas import metadata_payload_for_related_agents
from api.messaging.takeover import get_active_takeover, handle_inbound_during_takeover


DEFAULT_MCP_TOOL_NAMES = [
    "read_attachment",
    "list_attachments",
    "rag_query",
    "explore_web",
]


@dataclass
class AgentTaskDispatchResult:
    ok: bool
    response: JsonResponse | None = None
    task_id: str | None = None
    conversation_id: str | None = None
    takeover: bool = False
    agent_skipped: bool = False


def dispatch_conversation_agent_task(
    *,
    user,
    conversation_id: str,
    agent_slugs: list[str],
    user_inputs: list[dict[str, Any]],
    tool_names: list[str] | None = None,
    multiagentic_modality: str = "isolated",
    client_datetime: dict | None = None,
    regenerate_message_id: int | None = None,
    mcp_client_id: str | None = None,
) -> AgentTaskDispatchResult:
    """
    Validate and enqueue conversation_agent_task.

    Returns AgentTaskDispatchResult with either a JsonResponse error or task metadata.
    """
    from api.ai_layers.tasks import conversation_agent_task
    from api.ai_layers.tools import list_available_tools

    slugs = [s for s in agent_slugs if isinstance(s, str) and s.strip()]
    if not conversation_id:
        return AgentTaskDispatchResult(
            ok=False,
            response=JsonResponse({"error": "conversation_id is required"}, status=400),
        )
    if not slugs:
        return AgentTaskDispatchResult(
            ok=False,
            response=JsonResponse(
                {"error": "agent_slugs (at least one agent required)"},
                status=400,
            ),
        )
    if not user_inputs or not isinstance(user_inputs, list):
        return AgentTaskDispatchResult(
            ok=False,
            response=JsonResponse(
                {"error": "user_inputs (must be a non-empty list)"},
                status=400,
            ),
        )

    for i, inp in enumerate(user_inputs):
        if not isinstance(inp, dict) or "type" not in inp:
            return AgentTaskDispatchResult(
                ok=False,
                response=JsonResponse(
                    {
                        "error": (
                            f"user_inputs[{i}] must be an object with a 'type' field"
                        )
                    },
                    status=400,
                ),
            )

    tool_names = tool_names or []
    if not isinstance(tool_names, list):
        return AgentTaskDispatchResult(
            ok=False,
            response=JsonResponse(
                {"error": "tool_names must be a list of strings"},
                status=400,
            ),
        )

    if multiagentic_modality not in ("isolated", "grupal"):
        return AgentTaskDispatchResult(
            ok=False,
            response=JsonResponse(
                {"error": "multiagentic_modality must be 'isolated' or 'grupal'"},
                status=400,
            ),
        )

    available = list_available_tools()
    unknown = [t for t in tool_names if t not in available]
    if unknown:
        return AgentTaskDispatchResult(
            ok=False,
            response=JsonResponse(
                {
                    "error": f"Unknown tools: {', '.join(unknown)}",
                    "available_tools": available,
                },
                status=400,
            ),
        )

    user_org = get_user_organization(user)
    base_qs = accessible_agents_qs(user)
    agents_found = list(base_qs.filter(slug__in=slugs))
    found_slugs = {a.slug for a in agents_found}
    not_found = [s for s in slugs if s not in found_slugs]
    if not_found:
        return AgentTaskDispatchResult(
            ok=False,
            response=JsonResponse(
                {
                    "error": (
                        f"Agent(s) not found or not accessible: {', '.join(not_found)}"
                    )
                },
                status=404,
            ),
        )

    if any(a.agent_kind == AgentKind.PLATFORM_ASSISTANT for a in agents_found):
        return AgentTaskDispatchResult(
            ok=False,
            response=JsonResponse(
                {
                    "error": (
                        "Platform assistants must use "
                        "POST /api/ai_layers/agent-task/platform/"
                    ),
                },
                status=400,
            ),
        )

    try:
        conversation = Conversation.objects.get(id=conversation_id)
    except Conversation.DoesNotExist:
        return AgentTaskDispatchResult(
            ok=False,
            response=JsonResponse({"error": "Conversation not found"}, status=404),
        )

    conv_access_error = _validate_conversation_access(conversation, user, user_org)
    if conv_access_error:
        return AgentTaskDispatchResult(ok=False, response=conv_access_error)

    active_takeover = get_active_takeover(conversation)
    if active_takeover:
        handle_inbound_during_takeover(
            conversation,
            active_takeover,
            user_inputs,
            message_metadata={"human_takeover": True, "channel": "chat_app"},
        )
        return AgentTaskDispatchResult(
            ok=True,
            response=JsonResponse(
                {"status": "accepted", "takeover": True, "agent_skipped": True},
                status=202,
            ),
            conversation_id=str(conversation_id),
            takeover=True,
            agent_skipped=True,
        )

    by_slug = {a.slug: a for a in agents_found}
    agents_ordered = [by_slug[s] for s in slugs if s in by_slug]
    conversation.metadata = metadata_payload_for_related_agents(
        [a.id for a in agents_ordered]
    )
    conversation.save(update_fields=["metadata", "updated_at"])

    client_datetime, client_dt_error = _parse_client_datetime(client_datetime)
    if client_dt_error:
        return AgentTaskDispatchResult(ok=False, response=client_dt_error)

    regenerate_message_id, regen_error = _parse_regenerate_message_id(
        regenerate_message_id,
        conversation=conversation,
        user=user,
    )
    if regen_error:
        return AgentTaskDispatchResult(ok=False, response=regen_error)

    cache.delete(f"cancel_task_{conversation_id}")

    task = conversation_agent_task.delay(
        conversation_id=str(conversation_id),
        user_inputs=user_inputs,
        tool_names=tool_names,
        agent_slugs=slugs,
        multiagentic_modality=multiagentic_modality,
        user_id=user.id,
        regenerate_message_id=regenerate_message_id,
        client_datetime=client_datetime,
    )

    if mcp_client_id:
        cache.set(
            f"mcp_task_{task.id}",
            {
                "user_id": user.id,
                "mcp_client_id": mcp_client_id,
                "conversation_id": str(conversation_id),
            },
            timeout=3600,
        )

    return AgentTaskDispatchResult(
        ok=True,
        task_id=task.id,
        conversation_id=str(conversation_id),
    )
