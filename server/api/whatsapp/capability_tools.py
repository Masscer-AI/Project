"""WhatsApp line capabilities: any registered tool may be enabled; some are always on."""

from __future__ import annotations

# Always enabled on visitor WhatsApp lines (attachments, templates, tagging/cross-thread).
# Owners may enable any other tool from the registry at their own risk.
WHATSAPP_REQUIRED_CAPABILITY_TOOLS: tuple[str, ...] = (
    "read_attachment",
    "list_attachments",
    "list_document_templates",
    "raise_alert",
    "render_document_template",
    "query_organization_tags",
    "create_organization_tag",
    "change_conversation_tags",
    "change_conversation_summary",
    "get_tag_context",
    "query_conversation",
)


def filter_capabilities_for_whatsapp(capabilities: list | None) -> list[dict]:
    """Keep registered tools and enforce WhatsApp-required tools as enabled."""
    from api.ai_layers.tools import list_available_tools

    available = set(list_available_tools())
    out: list[dict] = []
    seen: set[str] = set()
    for cap in capabilities or []:
        if not isinstance(cap, dict):
            continue
        name = cap.get("name")
        if not isinstance(name, str) or name not in available:
            continue
        normalized = dict(cap)
        if name in WHATSAPP_REQUIRED_CAPABILITY_TOOLS:
            normalized["type"] = "internal_tool"
            normalized["enabled"] = True
        out.append(normalized)
        seen.add(name)

    for required_name in WHATSAPP_REQUIRED_CAPABILITY_TOOLS:
        if required_name in seen:
            continue
        if required_name not in available:
            continue
        out.append(
            {
                "name": required_name,
                "type": "internal_tool",
                "enabled": True,
            }
        )
    return out
