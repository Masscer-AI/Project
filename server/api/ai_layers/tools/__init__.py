"""
Agent tools for the AgentLoop.

Each tool module should export:
- A Pydantic BaseModel for its parameters
- The tool function itself
- A get_tool() helper that returns an AgentTool dict ready for AgentLoop

The TOOL_REGISTRY maps tool names to their module paths. When a Celery task
receives tool names as strings, resolve_tools() imports each module and calls
get_tool() to produce the AgentTool dicts that AgentLoop expects.
"""

from __future__ import annotations

import importlib
import json
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Registry: tool_name -> module path (must have a get_tool() function)
# ---------------------------------------------------------------------------

TOOL_REGISTRY: dict[str, str] = {
    "read_attachment": "api.ai_layers.tools.read_attachment",
    "list_attachments": "api.ai_layers.tools.list_attachments",
    "update_attachment_visibility": "api.ai_layers.tools.update_attachment_visibility",
    "explore_web": "api.ai_layers.tools.explore_web",
    "rag_query": "api.ai_layers.tools.rag_query",
    "list_knowledge_base_documents": "api.ai_layers.tools.list_knowledge_base_documents",
    "read_knowledge_base_document": "api.ai_layers.tools.read_knowledge_base_document",
    "create_image": "api.ai_layers.tools.create_image",
    "generate_video": "api.ai_layers.tools.generate_video",
    "create_speech": "api.ai_layers.tools.create_speech",
    "generate_dialogue": "api.ai_layers.tools.generate_dialogue",
    "list_voices": "api.ai_layers.tools.list_voices",
    "create_completion": "api.ai_layers.tools.create_completion",
    "read_plugin_instructions": "api.ai_layers.tools.read_plugin_instructions",
    "raise_alert": "api.ai_layers.tools.raise_alert",
    "query_organization_tags": "api.ai_layers.tools.query_organization_tags",
    "create_organization_tag": "api.ai_layers.tools.create_organization_tag",
    "change_conversation_tags": "api.ai_layers.tools.change_conversation_tags",
    "change_conversation_summary": "api.ai_layers.tools.change_conversation_summary",
    "get_tag_context": "api.ai_layers.tools.get_tag_context",
    "query_conversation": "api.ai_layers.tools.query_conversation",
    "list_conversations": "api.ai_layers.tools.list_conversations",
    "list_document_templates": "api.ai_layers.tools.list_document_templates",
    "render_document_template": "api.ai_layers.tools.render_document_template",
    "generate_document_file": "api.ai_layers.tools.generate_document_file",
    "generate_excel_file": "api.ai_layers.tools.generate_excel_file",
    "generate_gamma_presentation": "api.ai_layers.tools.generate_gamma_presentation",
    "send_email": "api.ai_layers.tools.send_email",
    "list_organization_members": "api.ai_layers.tools.list_organization_members",
    "list_organization_roles": "api.ai_layers.tools.list_organization_roles",
    "list_whatsapp_resources": "api.ai_layers.tools.list_whatsapp_resources",
    "list_whatsapp_templates": "api.ai_layers.tools.list_whatsapp_templates",
    "send_ws_template_message": "api.ai_layers.tools.send_ws_template_message",
    "list_calendar_events": "api.ai_layers.tools.list_calendar_events",
    "create_calendar_event": "api.ai_layers.tools.create_calendar_event",
    "update_calendar_event": "api.ai_layers.tools.update_calendar_event",
    "schedule_task": "api.ai_layers.tools.schedule_task",
    "list_scheduled_tasks": "api.ai_layers.tools.list_scheduled_tasks",
    "cancel_scheduled_task": "api.ai_layers.tools.cancel_scheduled_task",
    # Cloudbeds integration tools
    # "cloudbeds_list_hotels": "api.ai_layers.tools.cloudbeds_list_hotels",
}

WHATSAPP_TEMPLATE_AGENT_TOOL_NAMES: tuple[str, ...] = (
    "list_whatsapp_resources",
    "list_whatsapp_templates",
    "send_ws_template_message",
)

SCHEDULE_AGENT_TOOL_NAMES: tuple[str, ...] = (
    "schedule_task",
    "list_scheduled_tasks",
    "cancel_scheduled_task",
)

DEPENDENT_TOOL_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "list_voices": ("create_speech", "generate_dialogue"),
}

# Tools that act on behalf of an authenticated Masscer user (account-scoped
# calendar, org membership/roles, email-as-user, WhatsApp resource/template
# management, scheduled-task management, listing the actor's conversations).
# Never offered to anonymous callers (chat widget visitors, unlinked WhatsApp
# senders) — there is no Django User to scope them to. Org tagging /
# query_conversation are deliberately not listed here: WhatsApp may enable
# them for the line; widgets hard-strip them separately.
USER_REQUIRED_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "list_organization_members",
        "list_organization_roles",
        "list_conversations",
        "list_knowledge_base_documents",
        "read_knowledge_base_document",
        "update_attachment_visibility",
        "send_email",
        "list_whatsapp_resources",
        "list_whatsapp_templates",
        "send_ws_template_message",
        "list_calendar_events",
        "create_calendar_event",
        "update_calendar_event",
        "schedule_task",
        "list_scheduled_tasks",
        "cancel_scheduled_task",
    }
)

# Always removed on public chat-widget agent runs (even if saved on the widget).
# Shown disabled in the widget capabilities UI. Distinct from USER_REQUIRED:
# some of these can run on WhatsApp lines.
WIDGET_UNAVAILABLE_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "query_organization_tags",
        "create_organization_tag",
        "change_conversation_tags",
        "change_conversation_summary",
        "get_tag_context",
        "query_conversation",
        "list_conversations",
        "create_completion",
    }
)


def resolve_tools(tool_names: list[str], **context) -> list[dict]:
    """
    Resolve a list of tool name strings into AgentTool dicts.

    Each name is looked up in TOOL_REGISTRY, the corresponding module is
    imported, and its get_tool() function is called.

    Args:
        tool_names: list of registered tool names (e.g. ["read_attachment"])

    Returns:
        list of AgentTool dicts ready for ``AgentLoop.create(tools=[...], ...)``

    Unknown names are skipped. get_tool() failures are skipped so the agent
    can still run with the remaining tools.
    """
    # Stable dedupe (first occurrence wins). Gemini rejects duplicate function names.
    _seen: set[str] = set()
    unique_names: list[str] = []
    for n in tool_names:
        if n in _seen:
            continue
        _seen.add(n)
        unique_names.append(n)
    tool_names = [
        name for name in unique_names if name not in DEPENDENT_TOOL_REQUIREMENTS
    ]
    actor_user_id = context.get("user_id")
    for dependent_tool, required_tools in DEPENDENT_TOOL_REQUIREMENTS.items():
        if dependent_tool in USER_REQUIRED_TOOL_NAMES and actor_user_id is None:
            continue
        required_indexes = [
            tool_names.index(required_tool)
            for required_tool in required_tools
            if required_tool in tool_names
        ]
        if required_indexes:
            required_index = min(required_indexes)
            tool_names.insert(required_index + 1, dependent_tool)

    tools = []
    for name in tool_names:
        if name not in TOOL_REGISTRY:
            logger.warning(
                "Skipping unknown tool '%s'. Available: %s",
                name,
                ", ".join(sorted(TOOL_REGISTRY.keys())),
            )
            continue

        module_path = TOOL_REGISTRY[name]
        try:
            module = importlib.import_module(module_path)
            get_tool_fn = getattr(module, "get_tool")
            tools.append(get_tool_fn(**context))
            logger.info("Resolved tool '%s' from %s", name, module_path)
        except Exception as e:
            logger.error(
                "Failed to resolve tool '%s': %s. Skipping (agent will run without it).",
                name,
                e,
            )
            # Don't add the tool; continue with the rest
            continue

    _append_schedule_task_capability_catalog(tools)
    return tools


def _concise_tool_description(description: str, *, max_len: int = 160) -> str:
    text = " ".join((description or "").split())
    if not text:
        return ""
    first = text.split(". ", 1)[0].rstrip(".")
    if first:
        text = first + "."
    if len(text) > max_len:
        return text[: max_len - 1].rstrip() + "…"
    return text


def _append_schedule_task_capability_catalog(tools: list[dict]) -> None:
    """Tell schedule_task which tools it may optionally constrain the future run to."""
    schedule_tool = next((t for t in tools if t.get("name") == "schedule_task"), None)
    if schedule_tool is None:
        return

    from api.messaging.schedule_helpers import selectable_scheduled_task_tool_names

    # Prefer descriptions from currently resolved tools; fall back to bare names.
    by_name = {
        t.get("name"): _concise_tool_description(str(t.get("description") or ""))
        for t in tools
        if isinstance(t.get("name"), str) and t.get("name")
    }
    catalog: dict[str, str] = {}
    for name in selectable_scheduled_task_tool_names():
        catalog[name] = by_name.get(name) or name.replace("_", " ")

    if not catalog:
        return

    schedule_tool["description"] = (
        f"{schedule_tool.get('description', '').rstrip()} "
        "Optional tools allowlist names you may pass in tools "
        "(omit tools for all available; schedule-management tools are never available "
        "during execution): "
        f"(tool_name → description): {json.dumps(catalog, ensure_ascii=False)}"
    )


def list_registered_tools() -> list[str]:
    """All names in TOOL_REGISTRY, including dependent tools (list_voices, …)."""
    return sorted(TOOL_REGISTRY)


def list_available_tools() -> list[str]:
    """Tools that can be toggled in UIs (excludes dependents like list_voices)."""
    return sorted(set(TOOL_REGISTRY) - set(DEPENDENT_TOOL_REQUIREMENTS))


def resolve_allowed_tools(requested_names: list[str] | None, user) -> list[str]:
    """
    Shared validation/trust filter for every surface that turns a requested
    tool list into what an agent run may actually use.

    - Drops names not in TOOL_REGISTRY (dependent tools are allowed).
    - Drops names in USER_REQUIRED_TOOL_NAMES when user is None (no
      authenticated Masscer user backing this conversation, e.g. a public
      chat widget visitor or a WhatsApp sender).

    This does not enforce any per-surface or per-agent allowlist — callers
    are still responsible for deciding *which* names to request (widget
    capabilities, WhatsApp line capabilities, MCP credential allowlist,
    chat tool toggles). This function only enforces the trust floor.
    """
    registered = set(TOOL_REGISTRY)
    names: list[str] = []
    seen: set[str] = set()
    for name in requested_names or []:
        if not isinstance(name, str) or name not in registered:
            continue
        if name in seen:
            continue
        if user is None and name in USER_REQUIRED_TOOL_NAMES:
            continue
        seen.add(name)
        names.append(name)
    return names
