"""
Tools available only to compliance assistants (KYB e-sign).

Separate from the main chat TOOL_REGISTRY so conversational agents cannot
accidentally receive request_signature.
"""

from __future__ import annotations

import importlib
import logging

logger = logging.getLogger(__name__)

COMPLIANCE_TOOL_REGISTRY: dict[str, str] = {
    "read_attachment": "api.ai_layers.tools.read_attachment",
    "list_attachments": "api.ai_layers.tools.list_attachments",
    "request_signature": "api.ai_layers.tools.request_signature",
}


def resolve_compliance_tools(tool_names: list[str] | None = None, **context) -> list[dict]:
    """Resolve compliance tool names into AgentTool dicts."""
    names = tool_names if tool_names is not None else list(COMPLIANCE_TOOL_REGISTRY.keys())

    _seen: set[str] = set()
    unique_names: list[str] = []
    for n in names:
        if n in _seen:
            continue
        _seen.add(n)
        unique_names.append(n)

    tools = []
    for name in unique_names:
        if name not in COMPLIANCE_TOOL_REGISTRY:
            available = ", ".join(sorted(COMPLIANCE_TOOL_REGISTRY.keys()))
            raise ValueError(
                f"Unknown compliance tool '{name}'. Available: {available}"
            )
        module_path = COMPLIANCE_TOOL_REGISTRY[name]
        try:
            module = importlib.import_module(module_path)
            get_tool_fn = getattr(module, "get_tool")
            tools.append(get_tool_fn(**context))
        except Exception as e:
            logger.error("Failed to resolve compliance tool '%s': %s", name, e)
            continue
    return tools


def list_compliance_tools() -> list[str]:
    return sorted(COMPLIANCE_TOOL_REGISTRY.keys())
