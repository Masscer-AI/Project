"""OAuth configuration helpers."""

from __future__ import annotations

from django.conf import settings


def oauth_issuer() -> str:
    return (getattr(settings, "FRONTEND_URL", None) or "").strip().rstrip("/")


def mcp_resource_id() -> str:
    issuer = oauth_issuer()
    return f"{issuer}/mcp" if issuer else "/mcp"


def mcp_resource_ids() -> set[str]:
    """Canonical resource identifiers accepted for this MCP server."""
    issuer = oauth_issuer()
    if not issuer:
        return {"/mcp", "/mcp/"}
    return {f"{issuer}/mcp", f"{issuer}/mcp/"}


def resource_matches(resource: str | None) -> bool:
    if not resource:
        return False
    normalized = resource.strip().rstrip("/")
    allowed = {r.rstrip("/") for r in mcp_resource_ids()}
    return normalized in allowed
