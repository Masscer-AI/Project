"""
Tools available only to platform assistants (onboarding / org help).

Separate from the main chat TOOL_REGISTRY so conversational agents cannot
accidentally receive platform-only tools and vice versa.
"""

from __future__ import annotations

import importlib
import logging

logger = logging.getLogger(__name__)

PLATFORM_TOOL_REGISTRY: dict[str, str] = {
    "read_attachment": "api.ai_layers.tools.read_attachment",
    "list_attachments": "api.ai_layers.tools.list_attachments",
    "get_masscer_help_topic": "api.ai_layers.tools.get_masscer_help_topic",
    "list_masscer_help_topics": "api.ai_layers.tools.list_masscer_help_topics",
    "create_user_assignment": "api.ai_layers.tools.create_user_assignment",
    "list_user_assignments": "api.ai_layers.tools.list_user_assignments",
    "read_masscer_instructions": "api.ai_layers.tools.read_masscer_instructions",
}


def resolve_platform_tools(tool_names: list[str] | None = None, **context) -> list[dict]:
    """Resolve platform tool names into AgentTool dicts."""
    names = tool_names if tool_names is not None else list(PLATFORM_TOOL_REGISTRY.keys())

    _seen: set[str] = set()
    unique_names: list[str] = []
    for n in names:
        if n in _seen:
            continue
        _seen.add(n)
        unique_names.append(n)

    tools = []
    for name in unique_names:
        if name not in PLATFORM_TOOL_REGISTRY:
            available = ", ".join(sorted(PLATFORM_TOOL_REGISTRY.keys()))
            raise ValueError(
                f"Unknown platform tool '{name}'. Available: {available}"
            )
        module_path = PLATFORM_TOOL_REGISTRY[name]
        try:
            module = importlib.import_module(module_path)
            get_tool_fn = getattr(module, "get_tool")
            tools.append(get_tool_fn(**context))
        except Exception as e:
            logger.error("Failed to resolve platform tool '%s': %s", name, e)
            continue
    return tools


def list_platform_tools() -> list[str]:
    return sorted(PLATFORM_TOOL_REGISTRY.keys())
