"""Access helpers for inbound MCP external connections."""

from __future__ import annotations

import re

from django.db.models import Q
from django.utils.text import slugify

from api.ai_layers.access import accessible_agents_qs
from api.ai_layers.mcp_external_catalog import get_catalog_entry
from api.ai_layers.models import Agent, MCPExternalConnection

_SLUG_RE = re.compile(r"[^a-z0-9_-]+")


def sanitize_connection_slug(raw: str) -> str:
    slug = slugify(raw, allow_unicode=False).replace("-", "_")
    slug = _SLUG_RE.sub("_", slug.lower()).strip("_")
    return slug[:100] or "connection"


def prefixed_tool_name(connection: MCPExternalConnection, remote_tool_name: str) -> str:
    return f"{connection.slug}__{remote_tool_name}"


def parse_prefixed_tool_name(tool_name: str) -> tuple[str, str] | None:
    if "__" not in tool_name:
        return None
    slug, remote = tool_name.split("__", 1)
    if not slug or not remote:
        return None
    return slug, remote


def mcp_external_connections_qs(user, organization=None):
    """Connections owned by user and/or their organization."""
    q = Q(user=user, organization__isnull=True)
    if organization is not None:
        q |= Q(organization=organization, user__isnull=True)
    return (
        MCPExternalConnection.objects.filter(q, enabled=True, revoked=False)
        .prefetch_related("allowed_agents")
        .order_by("name")
    )


def mcp_external_connections_for_agent(
    agent: Agent,
    user,
    organization=None,
) -> list[MCPExternalConnection]:
    """Connections attached to this agent for the conversation owner context."""
    connections = list(mcp_external_connections_qs(user, organization))
    result: list[MCPExternalConnection] = []
    for conn in connections:
        allowed_ids = list(conn.allowed_agents.values_list("id", flat=True))
        if allowed_ids and agent.id not in allowed_ids:
            continue
        result.append(conn)
    return result


def resolve_remote_tools_for_connection(
    connection: MCPExternalConnection,
) -> list[dict]:
    """Return cached remote tool descriptors allowed for this connection."""
    cached = list(connection.cached_remote_tools or [])
    allowed = list(connection.allowed_remote_tool_names or [])
    if not allowed and connection.catalog_key:
        entry = get_catalog_entry(connection.catalog_key)
        if entry:
            allowed = list(entry.default_remote_tool_names)
    if allowed:
        allowed_set = set(allowed)
        cached = [t for t in cached if t.get("name") in allowed_set]
    return cached


def validate_agent_slugs_for_owner(
    user,
    organization,
    slugs: list[str],
) -> tuple[list[Agent] | None, str | None]:
    if not slugs:
        return [], None
    agents = list(accessible_agents_qs(user))
    if organization is not None:
        org_agents = list(
            accessible_agents_qs(user).filter(organization=organization)
        )
        slug_set = {a.slug for a in agents} | {a.slug for a in org_agents}
        allowed = {a.slug: a for a in agents}
        for a in org_agents:
            allowed[a.slug] = a
    else:
        slug_set = {a.slug for a in agents}
        allowed = {a.slug: a for a in agents}
    invalid = [s for s in slugs if s not in slug_set]
    if invalid:
        return None, f"Agent(s) not accessible: {', '.join(invalid)}"
    return [allowed[s] for s in slugs], None


def normalize_remote_tool_names(
    raw: list | None,
    connection: MCPExternalConnection,
) -> tuple[list[str] | None, str | None]:
    if raw is None:
        return [], None
    if not isinstance(raw, list):
        return None, "allowed_remote_tool_names must be a list of strings"
    cached_names = {t.get("name") for t in (connection.cached_remote_tools or []) if t.get("name")}
    if not cached_names and connection.catalog_key:
        entry = get_catalog_entry(connection.catalog_key)
        if entry:
            cached_names = set(entry.default_remote_tool_names)
    names: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            continue
        name = item.strip()
        if cached_names and name not in cached_names:
            return None, f"Unknown remote tool: {name}"
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names, None
