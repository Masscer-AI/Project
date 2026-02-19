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
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Registry: tool_name -> module path (must have a get_tool() function)
# ---------------------------------------------------------------------------

TOOL_REGISTRY: dict[str, str] = {
    "print_color": "api.ai_layers.tools.print_color",
    "read_attachment": "api.ai_layers.tools.read_attachment",
    "list_attachments": "api.ai_layers.tools.list_attachments",
    "explore_web": "api.ai_layers.tools.explore_web",
    "rag_query": "api.ai_layers.tools.rag_query",
}


def resolve_tools(tool_names: list[str], **context) -> list[dict]:
    """
    Resolve a list of tool name strings into AgentTool dicts.

    Each name is looked up in TOOL_REGISTRY, the corresponding module is
    imported, and its get_tool() function is called.

    Args:
        tool_names: list of registered tool names (e.g. ["print_color"])

    Returns:
        list of AgentTool dicts ready for AgentLoop(tools=[...])

    Raises:
        ValueError: if a tool name is not found in the registry
        AttributeError: if a tool module doesn't export get_tool()
    """
    tools = []
    for name in tool_names:
        if name not in TOOL_REGISTRY:
            available = ", ".join(sorted(TOOL_REGISTRY.keys()))
            raise ValueError(
                f"Unknown tool '{name}'. Available tools: {available}"
            )

        module_path = TOOL_REGISTRY[name]
        try:
            module = importlib.import_module(module_path)
            get_tool_fn = getattr(module, "get_tool")
            tools.append(get_tool_fn(**context))
            logger.info("Resolved tool '%s' from %s", name, module_path)
        except Exception as e:
            logger.error("Failed to resolve tool '%s': %s", name, e)
            raise

    return tools


def list_available_tools() -> list[str]:
    """Return a sorted list of all registered tool names."""
    return sorted(TOOL_REGISTRY.keys())
