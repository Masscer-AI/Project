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
    """Keep only allowed tools; drop unknown or frontend-only capabilities."""
    out: list[dict] = []
    for cap in capabilities or []:
        if not isinstance(cap, dict):
            continue
        name = cap.get("name")
        if not isinstance(name, str) or name not in WHATSAPP_ALLOWED_CAPABILITY_TOOLS:
            continue
        out.append(cap)
    return out
