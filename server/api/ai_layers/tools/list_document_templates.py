"""
Tool: list_document_templates

Returns templates assigned to the current agent (enabled only), including
placeholder names and variable descriptions from metadata.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ListDocumentTemplatesParams(BaseModel):
    """No required parameters."""

    include_variables: bool = Field(
        default=True,
        description="If true, include per-variable descriptions and required flags.",
    )


def _list_impl(
    *,
    conversation_id: str,
    agent_slug: str | None,
    organization_id: str | None,
    include_variables: bool = True,
) -> str:
    from api.ai_layers.models import Agent
    from api.document_templates.models import AgentDocumentTemplateAssignment
    from api.messaging.models import Conversation

    if not agent_slug:
        raise ValueError("agent_slug is required in tool context")
    try:
        Conversation.objects.get(id=conversation_id)
    except Conversation.DoesNotExist:
        raise ValueError("Conversation not found")

    agent = Agent.objects.filter(slug=agent_slug).select_related("organization").first()
    if not agent:
        raise ValueError("Agent not found")

    qs = (
        AgentDocumentTemplateAssignment.objects.filter(
            agent=agent, is_enabled=True, template__is_active=True
        )
        .select_related("template")
        .order_by("template__name")
    )
    out: list[dict[str, Any]] = []
    for a in qs:
        t = a.template
        md = t.metadata or {}
        placeholders = md.get("placeholders") if isinstance(md.get("placeholders"), list) else []
        variables = md.get("variables") if isinstance(md.get("variables"), dict) else {}
        item: dict[str, Any] = {
            "template_id": str(t.id),
            "name": t.name,
            "description": t.description,
            "usage_instructions": a.usage_instructions,
            "placeholders": placeholders,
        }
        if include_variables:
            item["variables"] = variables
        out.append(item)
    return json.dumps({"templates": out}, ensure_ascii=False)


def get_tool(
    conversation_id: str | None = None,
    agent_slug: str | None = None,
    organization_id: str | None = None,
    **kwargs,
) -> dict:
    if not conversation_id:
        raise ValueError("list_document_templates requires conversation_id in tool context")

    def list_document_templates(include_variables: bool = True) -> str:
        return _list_impl(
            conversation_id=conversation_id,
            agent_slug=agent_slug,
            organization_id=organization_id,
            include_variables=include_variables,
        )

    return {
        "name": "list_document_templates",
        "description": (
            "List Word document templates attached to this agent. "
            "Each entry includes template_id, placeholders, and variable descriptions. "
            "Call before render_document_template when you need the exact schema."
        ),
        "parameters": ListDocumentTemplatesParams,
        "function": list_document_templates,
    }
