"""Which internal tools may be enabled on a WhatsApp line (visitor-facing channel)."""

from __future__ import annotations

# Plugins (mermaid, etc.) and document templates are web-chat only — not visible on WhatsApp.
WHATSAPP_ALLOWED_CAPABILITY_TOOLS: frozenset[str] = frozenset(
    {
        "read_attachment",
        "list_attachments",
        "explore_web",
        "rag_query",
        "create_image",
        "create_speech",
        "generate_video",
    }
)

WHATSAPP_REQUIRED_CAPABILITY_TOOLS: tuple[str, str] = (
    "read_attachment",
    "list_attachments",
)

WHATSAPP_DISALLOWED_CAPABILITY_TOOLS: frozenset[str] = frozenset(
    {
        "read_plugin_instructions",
        "raise_alert",
        "list_document_templates",
        "render_document_template",
        "create_completion",
        "query_organization_tags",
        "create_organization_tag",
        "change_conversation_tags",
        "change_conversation_summary",
        "get_tag_context",
        "query_conversation",
    }
)


def filter_capabilities_for_whatsapp(capabilities: list | None) -> list[dict]:
    """Keep only allowed tools and enforce WhatsApp-required tools as enabled."""
    out: list[dict] = []
    seen: set[str] = set()
    for cap in capabilities or []:
        if not isinstance(cap, dict):
            continue
        name = cap.get("name")
        if not isinstance(name, str) or name not in WHATSAPP_ALLOWED_CAPABILITY_TOOLS:
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
        out.append(
            {
                "name": required_name,
                "type": "internal_tool",
                "enabled": True,
            }
        )
    return out
