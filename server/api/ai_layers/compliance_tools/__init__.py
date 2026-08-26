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
    "update_attachment_visibility": "api.ai_layers.tools.update_attachment_visibility",
    "list_knowledge_base_documents": "api.ai_layers.tools.list_knowledge_base_documents",
    "read_knowledge_base_document": "api.ai_layers.tools.read_knowledge_base_document",
    "rag_query": "api.ai_layers.tools.rag_query",
    "generate_gamma_attachment": "api.ai_layers.tools.generate_gamma_presentation",
    "generate_document_file": "api.ai_layers.tools.generate_document_file",
    "list_document_templates": "api.ai_layers.tools.list_document_templates",
    "render_document_template": "api.ai_layers.tools.render_document_template",
    "generate_excel_file": "api.ai_layers.tools.generate_excel_file",
    "request_signature": "api.ai_layers.tools.request_signature",
    "explore_web": "api.ai_layers.tools.explore_web",
    "send_email": "api.ai_layers.tools.send_email",
    "list_organization_members": "api.ai_layers.tools.list_organization_members",
    "list_organization_roles": "api.ai_layers.tools.list_organization_roles",
    "change_conversation_summary": "api.ai_layers.tools.change_conversation_summary",
    "query_organization_tags": "api.ai_layers.tools.query_organization_tags",
    "create_organization_tag": "api.ai_layers.tools.create_organization_tag",
    "change_conversation_tags": "api.ai_layers.tools.change_conversation_tags",
    "get_tag_context": "api.ai_layers.tools.get_tag_context",
    "create_user_assignment": "api.ai_layers.tools.create_user_assignment",
    "list_user_assignments": "api.ai_layers.tools.list_user_assignments",
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
