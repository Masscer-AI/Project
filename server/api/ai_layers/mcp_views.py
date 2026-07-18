"""
MCP gateway HTTP endpoints (authenticated via MCPClient Bearer tokens).

These endpoints are called by the FastAPI MCP protocol server, not directly by
external MCP clients in production.
"""

from __future__ import annotations

import json
import logging

from celery.result import AsyncResult
from django.core.cache import cache
from django.http import FileResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from api.ai_layers.agent_task_dispatch import dispatch_conversation_agent_task
from api.ai_layers.mcp_access import (
    MCP_TOOL_PRESETS,
    agent_to_mcp_tool_payload,
    get_mcp_user_org,
    mcp_accessible_agents_qs,
    normalize_mcp_tool_names,
    public_mcp_url,
    resolve_mcp_agent,
    resolve_mcp_tool_names,
    sanitize_mcp_tool_name,
    serialize_attachments_for_mcp,
    verify_mcp_attachment_download_token,
)
from api.ai_layers.models import MCPClient
from api.authenticate.decorators.mcp_token_required import (
    authenticate_mcp_request,
    mcp_token_required,
)
from api.authenticate.decorators.token_required import token_required
from api.integrations.services import get_user_organization, user_can_manage_integrations
from api.messaging.models import Conversation

logger = logging.getLogger(__name__)


def _require_integrations_management(request):
    org = get_user_organization(request.user)
    if not user_can_manage_integrations(request.user, org):
        return JsonResponse(
            {
                "error": (
                    "The 'can-manage-integrations' feature is not enabled "
                    "for your account."
                )
            },
            status=403,
        )
    return None


def _mcp_task_authorized(request, task_id: str) -> bool:
    meta = cache.get(f"mcp_task_{task_id}")
    if not meta:
        return False
    return (
        meta.get("user_id") == request.user.id
        and meta.get("mcp_client_id") == str(request.mcp_client.id)
    )


@csrf_exempt
@mcp_token_required
@require_http_methods(["GET"])
def mcp_list_agents(request):
    """List agents exposed as MCP tools for this credential."""
    agents = list(mcp_accessible_agents_qs(request.mcp_client))
    return JsonResponse(
        {
            "agents": [agent_to_mcp_tool_payload(a) for a in agents],
        }
    )


@csrf_exempt
@mcp_token_required
@require_http_methods(["POST"])
def mcp_run_agent(request):
    """
    Dispatch a Masscer agent via the production AgentLoop.

    Body: { "agent_slug": "...", "message": "...", "conversation_id": "..."? }
    """
    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    agent_slug = (data.get("agent_slug") or "").strip()
    message = (data.get("message") or "").strip()
    conversation_id = data.get("conversation_id")

    if not agent_slug:
        return JsonResponse({"error": "agent_slug is required"}, status=400)
    if not message:
        return JsonResponse({"error": "message is required"}, status=400)

    agent = resolve_mcp_agent(request.mcp_client, agent_slug)
    if not agent:
        return JsonResponse(
            {"error": f"Agent '{agent_slug}' not found or not accessible"},
            status=404,
        )

    user = request.user
    mcp_client = request.mcp_client

    if conversation_id:
        try:
            conversation = Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            return JsonResponse({"error": "Conversation not found"}, status=404)
        from api.ai_layers.agent_task_helpers import validate_conversation_access

        err = validate_conversation_access(
            conversation, user, get_mcp_user_org(mcp_client)
        )
        if err:
            return err
    else:
        org = mcp_client.organization
        metadata = {
            "source": "mcp",
            "mcp_client_id": str(mcp_client.id),
            "related_agents": [agent.id],
        }
        conversation = Conversation.objects.create(
            user=user,
            organization=org,
            metadata=metadata,
        )
        conversation_id = str(conversation.id)

    result = dispatch_conversation_agent_task(
        user=user,
        conversation_id=str(conversation_id),
        agent_slugs=[agent.slug],
        user_inputs=[{"type": "input_text", "text": message}],
        tool_names=resolve_mcp_tool_names(mcp_client),
        multiagentic_modality="isolated",
        mcp_client_id=str(mcp_client.id),
    )

    if not result.ok:
        return result.response

    if result.takeover:
        return result.response

    return JsonResponse(
        {
            "task_id": result.task_id,
            "conversation_id": result.conversation_id,
            "status": "accepted",
            "tool_name": sanitize_mcp_tool_name(agent.slug),
        },
        status=202,
    )


@csrf_exempt
@mcp_token_required
@require_http_methods(["GET"])
def mcp_task_result(request, task_id: str):
    """Poll Celery task result for an MCP-dispatched agent run."""
    if not _mcp_task_authorized(request, task_id):
        return JsonResponse({"error": "Task not found or access denied"}, status=404)

    async_result = AsyncResult(task_id)

    if not async_result.ready():
        return JsonResponse({"status": "pending", "task_id": task_id})

    if async_result.failed():
        err = str(async_result.result) if async_result.result else "Task failed"
        return JsonResponse(
            {"status": "failed", "task_id": task_id, "error": err},
            status=500,
        )

    payload = async_result.result or {}
    if not isinstance(payload, dict):
        return JsonResponse(
            {
                "status": "completed",
                "task_id": task_id,
                "output": str(payload),
            }
        )

    attachments = serialize_attachments_for_mcp(
        request, payload.get("attachments") or []
    )

    return JsonResponse(
        {
            "status": payload.get("status", "completed"),
            "task_id": task_id,
            "output": payload.get("output", ""),
            "message_id": payload.get("message_id"),
            "iterations": payload.get("iterations"),
            "tool_calls_count": payload.get("tool_calls_count"),
            "attachments": attachments,
            "conversation_id": cache.get(f"mcp_task_{task_id}", {}).get(
                "conversation_id"
            ),
        }
    )


# ─── Credential management (user Token auth, for UI) ─────────────────────────


def _credential_summary(c, *, auth_via_oauth: bool | None = None) -> dict:
    allowed = list(c.allowed_agents.values_list("slug", flat=True))
    if auth_via_oauth is None:
        auth_via_oauth = bool(
            getattr(c, "_has_oauth_access", False)
            or getattr(c, "_has_oauth_refresh", False)
        )
    return {
        "id": str(c.id),
        "name": c.name,
        "created_at": c.created_at.isoformat(),
        "last_used_at": c.last_used_at.isoformat() if c.last_used_at else None,
        "allowed_agent_slugs": allowed,
        "allowed_tool_names": list(c.allowed_tool_names or []),
        "key_prefix": c.key[:8] + "…" if c.key else None,
        "auth_via_oauth": bool(auth_via_oauth),
    }


@csrf_exempt
@require_http_methods(["GET"])
def mcp_download_attachment(request, attachment_id):
    """
    Download a file attachment via:
    - Authorization: Bearer (MCP key / OAuth), with conversation access checks, or
    - ?token= short-lived signed capability URL (no Bearer; ~1h expiry).
    """
    from api.ai_layers.agent_task_helpers import validate_conversation_access
    from api.messaging.models import MessageAttachment

    signed_token = (request.GET.get("token") or "").strip()
    if signed_token:
        verified_id = verify_mcp_attachment_download_token(signed_token)
        if verified_id is None or str(verified_id) != str(attachment_id):
            return JsonResponse(
                {"error": "Invalid or expired download token"},
                status=401,
            )
    else:
        auth_error = authenticate_mcp_request(request)
        if auth_error is not None:
            return auth_error

    try:
        attachment = MessageAttachment.objects.select_related(
            "conversation",
            "conversation__organization",
            "conversation__user",
        ).get(id=attachment_id)
    except MessageAttachment.DoesNotExist:
        return JsonResponse({"error": "Attachment not found"}, status=404)

    if not signed_token:
        err = validate_conversation_access(
            attachment.conversation,
            request.user,
            get_mcp_user_org(request.mcp_client),
        )
        if err:
            return err

    if attachment.kind != "file" or not attachment.file:
        return JsonResponse(
            {"error": "Attachment is not a downloadable file"},
            status=400,
        )

    filename = (attachment.metadata or {}).get("name") or attachment.file.name.split("/")[-1]
    response = FileResponse(
        attachment.file.open("rb"),
        content_type=attachment.content_type or "application/octet-stream",
    )
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


@csrf_exempt
@token_required
@require_http_methods(["GET"])
def mcp_tool_presets(request):
    """Return MCP tool preset groupings for the Integrations UI."""
    denied = _require_integrations_management(request)
    if denied:
        return denied

    from api.ai_layers.mcp_access import mcp_all_tool_names, mcp_tool_preset_groups

    return JsonResponse(
        {
            "presets": {
                name: list(tools) for name, tools in MCP_TOOL_PRESETS.items()
            },
            "groups": mcp_tool_preset_groups(),
            "all_tools": mcp_all_tool_names(),
        }
    )


@csrf_exempt
@token_required
@require_http_methods(["GET", "POST"])
def mcp_credentials(request):
    """List or create MCP credentials for the authenticated user."""
    denied = _require_integrations_management(request)
    if denied:
        return denied

    user = request.user

    if request.method == "GET":
        from django.db.models import Exists, OuterRef

        from api.mcp_oauth.models import OAuthAccessToken, OAuthRefreshToken

        clients = (
            MCPClient.objects.filter(user=user, revoked=False)
            .prefetch_related("allowed_agents")
            .annotate(
                _has_oauth_access=Exists(
                    OAuthAccessToken.objects.filter(mcp_client_id=OuterRef("pk"))
                ),
                _has_oauth_refresh=Exists(
                    OAuthRefreshToken.objects.filter(mcp_client_id=OuterRef("pk"))
                ),
            )
        )
        data = [_credential_summary(c) for c in clients]
        return JsonResponse({"credentials": data})

    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    name = (body.get("name") or "").strip()
    if not name:
        return JsonResponse({"error": "name is required"}, status=400)

    allowed_slugs = body.get("allowed_agent_slugs") or []
    if allowed_slugs and not isinstance(allowed_slugs, list):
        return JsonResponse(
            {"error": "allowed_agent_slugs must be a list of slugs"},
            status=400,
        )

    allowed_tool_names_raw = body.get("allowed_tool_names")
    if allowed_tool_names_raw is not None and not isinstance(allowed_tool_names_raw, list):
        return JsonResponse(
            {"error": "allowed_tool_names must be a list of tool names"},
            status=400,
        )
    tool_names, tool_err = normalize_mcp_tool_names(allowed_tool_names_raw)
    if tool_err:
        return JsonResponse({"error": tool_err}, status=400)

    org = get_mcp_user_org_for_user(user)
    mcp_client = MCPClient.objects.create(
        name=name,
        user=user,
        organization=org,
        allowed_tool_names=tool_names or [],
    )

    if allowed_slugs:
        agents = list(mcp_accessible_agents_qs_for_user(user, mcp_client=None))
        slug_set = {a.slug for a in agents}
        invalid = [s for s in allowed_slugs if s not in slug_set]
        if invalid:
            mcp_client.delete()
            return JsonResponse(
                {
                    "error": (
                        f"Agent(s) not accessible: {', '.join(invalid)}"
                    )
                },
                status=400,
            )
        allowed = [a for a in agents if a.slug in allowed_slugs]
        mcp_client.allowed_agents.set(allowed)

    mcp_url = public_mcp_url(request)

    return JsonResponse(
        {
            "id": str(mcp_client.id),
            "name": mcp_client.name,
            "key": mcp_client.key,
            "mcp_url": mcp_url,
            "allowed_agent_slugs": list(
                mcp_client.allowed_agents.values_list("slug", flat=True)
            ),
            "allowed_tool_names": list(mcp_client.allowed_tool_names or []),
            "mcp_config": {
                "mcpServers": {
                    f"masscer-{name}": {
                        "url": mcp_url,
                        "headers": {
                            "Authorization": f"Bearer {mcp_client.key}",
                        },
                    }
                }
            },
            "claude_instructions": (
                "In Claude: Settings → Connectors → Add custom connector. "
                f"Enter URL: {mcp_url}. "
                "Use the Bearer token as authentication if prompted."
            ),
        },
        status=201,
    )


def get_mcp_user_org_for_user(user):
    from api.ai_layers.access import get_user_organization

    return get_user_organization(user)


def mcp_accessible_agents_qs_for_user(user, mcp_client=None):
    from api.ai_layers.access import accessible_agents_qs
    from api.ai_layers.models import AgentKind

    return accessible_agents_qs(user).filter(
        agent_kind=AgentKind.CONVERSATIONAL_AGENT
    )


@csrf_exempt
@token_required
@require_http_methods(["DELETE", "PATCH"])
def mcp_credential_detail(request, credential_id):
    """Revoke or update an MCP credential."""
    denied = _require_integrations_management(request)
    if denied:
        return denied

    try:
        mcp_client = MCPClient.objects.get(id=credential_id, user=request.user)
    except MCPClient.DoesNotExist:
        return JsonResponse({"error": "Credential not found"}, status=404)

    if request.method == "DELETE":
        mcp_client.revoked = True
        mcp_client.save(update_fields=["revoked", "updated_at"])
        return JsonResponse({"status": "revoked", "id": str(mcp_client.id)})

    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    update_fields = ["updated_at"]

    if "name" in body:
        name = (body.get("name") or "").strip()
        if not name:
            return JsonResponse({"error": "name cannot be empty"}, status=400)
        mcp_client.name = name
        update_fields.append("name")

    if "allowed_agent_slugs" in body:
        allowed_slugs = body.get("allowed_agent_slugs") or []
        if not isinstance(allowed_slugs, list):
            return JsonResponse(
                {"error": "allowed_agent_slugs must be a list of slugs"},
                status=400,
            )
        agents = list(mcp_accessible_agents_qs_for_user(request.user))
        slug_set = {a.slug for a in agents}
        invalid = [s for s in allowed_slugs if s not in slug_set]
        if invalid:
            return JsonResponse(
                {"error": f"Agent(s) not accessible: {', '.join(invalid)}"},
                status=400,
            )
        allowed = [a for a in agents if a.slug in allowed_slugs]
        mcp_client.allowed_agents.set(allowed)

    if "allowed_tool_names" in body:
        tool_names, tool_err = normalize_mcp_tool_names(body.get("allowed_tool_names"))
        if tool_err:
            return JsonResponse({"error": tool_err}, status=400)
        mcp_client.allowed_tool_names = tool_names or []
        update_fields.append("allowed_tool_names")

    mcp_client.save(update_fields=update_fields)
    return JsonResponse(_credential_summary(mcp_client))


@csrf_exempt
@token_required
@require_http_methods(["GET"])
def mcp_connection_config(request):
    """
    Return MCP connection info for an existing credential (by id) or template.
    Query: ?credential_id=<uuid>
    """
    denied = _require_integrations_management(request)
    if denied:
        return denied

    credential_id = request.GET.get("credential_id")
    if not credential_id:
        return JsonResponse({"error": "credential_id is required"}, status=400)

    try:
        mcp_client = MCPClient.objects.get(
            id=credential_id, user=request.user, revoked=False
        )
    except MCPClient.DoesNotExist:
        return JsonResponse({"error": "Credential not found"}, status=404)

    mcp_url = public_mcp_url(request)

    return JsonResponse(
        {
            "mcp_url": mcp_url,
            "key": mcp_client.key,
            "name": mcp_client.name,
            "mcp_config_json": json.dumps(
                {
                    "mcpServers": {
                        f"masscer-{mcp_client.name}": {
                            "url": mcp_url,
                            "headers": {
                                "Authorization": f"Bearer {mcp_client.key}",
                            },
                        }
                    }
                },
                indent=2,
            ),
            "claude_instructions": (
                "Claude: Settings → Connectors → Add custom connector. "
                f"URL: {mcp_url}"
            ),
        }
    )
