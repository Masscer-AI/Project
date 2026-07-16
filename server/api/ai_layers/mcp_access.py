from __future__ import annotations

import re
from datetime import datetime, timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.utils import timezone

from api.ai_layers.access import accessible_agents_qs, get_user_organization
from api.ai_layers.models import Agent, AgentKind, MCPClient

_SLUG_RE = re.compile(r"[^a-z0-9_]+")

MCP_ATTACHMENT_DOWNLOAD_TOKEN_SALT = "mcp-attachment-download"
MCP_ATTACHMENT_DOWNLOAD_MAX_AGE_SEC = 60 * 60  # 1 hour


def public_app_base_url(request=None) -> str:
    """Public app origin for MCP and other client-facing URLs."""
    frontend = (getattr(settings, "FRONTEND_URL", None) or "").strip().rstrip("/")
    if frontend:
        return frontend
    if request is not None:
        return request.build_absolute_uri("/").rstrip("/")
    return ""


def public_mcp_url(request=None) -> str:
    base = public_app_base_url(request)
    return f"{base}/mcp/" if base else "/mcp/"


def _attachment_download_signer() -> TimestampSigner:
    return TimestampSigner(salt=MCP_ATTACHMENT_DOWNLOAD_TOKEN_SALT)


def mint_mcp_attachment_download_token(attachment_id: str) -> tuple[str, datetime]:
    """Return (signed token, expires_at) for a short-lived public download link."""
    expires_at = timezone.now() + timedelta(seconds=MCP_ATTACHMENT_DOWNLOAD_MAX_AGE_SEC)
    token = _attachment_download_signer().sign(str(attachment_id))
    return token, expires_at


def verify_mcp_attachment_download_token(token: str) -> str | None:
    """Return attachment_id if token is valid and unexpired, else None."""
    if not token:
        return None
    try:
        return _attachment_download_signer().unsign(
            token, max_age=MCP_ATTACHMENT_DOWNLOAD_MAX_AGE_SEC
        )
    except (BadSignature, SignatureExpired):
        return None


def mcp_attachment_signed_download_url(
    request, attachment_id: str
) -> tuple[str, datetime] | None:
    """
    Public absolute download URL using FRONTEND_URL + short-lived signed token.
    Returns None when no public base URL is configured.
    """
    base = public_app_base_url(request)
    if not base:
        return None
    token, expires_at = mint_mcp_attachment_download_token(str(attachment_id))
    query = urlencode({"token": token})
    url = f"{base}/v1/ai_layers/mcp/attachments/{attachment_id}/?{query}"
    return url, expires_at

MCP_BASIC_TOOL_NAMES: tuple[str, ...] = (
    "read_attachment",
    "list_attachments",
    "rag_query",
    "explore_web",
)

MCP_MEDIA_TOOL_NAMES: tuple[str, ...] = (
    "create_image",
    "create_speech",
    "generate_video",
    "generate_dialogue",
)

MCP_DOCUMENT_TOOL_NAMES: tuple[str, ...] = (
    "generate_document_file",
    "generate_excel_file",
    "list_document_templates",
    "render_document_template",
)

MCP_TOOL_PRESETS: dict[str, tuple[str, ...]] = {
    "basic": MCP_BASIC_TOOL_NAMES,
    "media": MCP_MEDIA_TOOL_NAMES,
    "documents": MCP_DOCUMENT_TOOL_NAMES,
}


def sanitize_mcp_tool_name(agent_slug: str) -> str:
    """Map agent slug to MCP tool name: ask_<sanitized_slug>."""
    sanitized = _SLUG_RE.sub("_", agent_slug.lower()).strip("_")
    return f"ask_{sanitized}"


def tool_name_to_agent_slug(tool_name: str) -> str | None:
    if not tool_name.startswith("ask_"):
        return None
    return tool_name[len("ask_") :]


def mcp_accessible_agents_qs(mcp_client: MCPClient):
    """Agents this MCP credential may expose (user access ∩ optional allowlist)."""
    user = mcp_client.user
    qs = accessible_agents_qs(user).filter(agent_kind=AgentKind.CONVERSATIONAL_AGENT)
    allowed_ids = list(mcp_client.allowed_agents.values_list("id", flat=True))
    if allowed_ids:
        qs = qs.filter(id__in=allowed_ids)
    return qs.distinct()


def normalize_mcp_tool_names(raw: list | None) -> tuple[list[str] | None, str | None]:
    """
    Validate and dedupe tool names for storage on MCPClient.
    Empty list means "use basic preset at runtime".
    """
    if raw is None:
        return [], None
    if not isinstance(raw, list):
        return None, "allowed_tool_names must be a list of strings"

    from api.ai_layers.tools import list_available_tools

    available = set(list_available_tools())
    names: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            continue
        name = item.strip()
        if name not in available:
            return None, f"Unknown tool: {name}"
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names, None


def resolve_mcp_tool_names(mcp_client: MCPClient) -> list[str]:
    """Resolve agent tool allowlist for an MCP credential run."""
    stored = list(mcp_client.allowed_tool_names or [])
    if not stored:
        return list(MCP_BASIC_TOOL_NAMES)
    return stored


# Fields exposed to MCP clients in agent tool results (plus signed download_url).
_MCP_ATTACHMENT_FIELDS = frozenset(
    {"attachment_id", "type", "name", "content_type", "text"}
)


def serialize_attachments_for_mcp(request, attachments: list | None) -> list[dict]:
    """
    Client-safe attachment metadata for MCP tool results.

    Strips internal media paths. Adds a short-lived absolute download_url
    (FRONTEND_URL + signed token, ~1h) when a public base URL is available.
    """
    result: list[dict] = []
    for att in attachments or []:
        if not isinstance(att, dict):
            continue
        item = {k: v for k, v in att.items() if k in _MCP_ATTACHMENT_FIELDS and v}
        aid = item.get("attachment_id")
        if not aid:
            continue
        signed = mcp_attachment_signed_download_url(request, str(aid))
        if signed:
            url, expires_at = signed
            item["download_url"] = url
            item["expires_at"] = expires_at.isoformat()
        result.append(item)
    return result


def agent_to_mcp_tool_payload(agent: Agent) -> dict:
    description = agent.act_as[:500] if agent.act_as else f"Masscer agent: {agent.name}"
    return {
        "slug": agent.slug,
        "name": agent.name,
        "tool_name": sanitize_mcp_tool_name(agent.slug),
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The message or question to send to the agent",
                },
                "conversation_id": {
                    "type": "string",
                    "description": (
                        "Optional conversation UUID for multi-turn context. "
                        "Omit to start a new MCP conversation."
                    ),
                },
            },
            "required": ["message"],
        },
    }


def resolve_mcp_agent(mcp_client: MCPClient, agent_slug: str) -> Agent | None:
    return mcp_accessible_agents_qs(mcp_client).filter(slug=agent_slug).first()


def resolve_mcp_agent_by_tool_name(mcp_client: MCPClient, tool_name: str) -> Agent | None:
    slug = tool_name_to_agent_slug(tool_name)
    if not slug:
        return None
    agents = list(mcp_accessible_agents_qs(mcp_client))
    for agent in agents:
        if sanitize_mcp_tool_name(agent.slug) == tool_name:
            return agent
    return None


def get_mcp_user_org(mcp_client: MCPClient):
    return mcp_client.organization or get_user_organization(mcp_client.user)
