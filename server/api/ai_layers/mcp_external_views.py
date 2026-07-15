"""CRUD API for inbound MCP external connections (Integrations UI)."""

from __future__ import annotations

import json
import logging

from django.utils import timezone

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from api.ai_layers.mcp_external_access import (
    mcp_external_connections_qs,
    normalize_remote_tool_names,
    sanitize_connection_slug,
    validate_agent_slugs_for_owner,
)
from api.ai_layers.mcp_external_catalog import (
    catalog_entry_to_dict,
    get_catalog_entry,
    list_catalog_entries,
)
from api.ai_layers.mcp_outbound_client import list_external_mcp_tools
from api.ai_layers.models import MCPExternalConnection
from api.authenticate.decorators.token_required import token_required
from api.integrations.services import get_user_organization, user_can_manage_integrations

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


def _connection_owner_for_create(user, body: dict):
    org = get_user_organization(user)
    owner_type = (body.get("owner_type") or "user").strip().lower()
    if owner_type == "organization":
        if not org:
            return None, None, JsonResponse(
                {"error": "No organization available for org-scoped connection"},
                status=400,
            )
        return None, org, None
    return user, None, None


def _connections_visible_to_user(user):
    org = get_user_organization(user)
    return mcp_external_connections_qs(user, org)


def _connection_summary(conn: MCPExternalConnection) -> dict:
    return {
        "id": str(conn.id),
        "name": conn.name,
        "slug": conn.slug,
        "catalog_key": conn.catalog_key,
        "transport": conn.transport,
        "allowed_agent_slugs": list(conn.allowed_agents.values_list("slug", flat=True)),
        "allowed_remote_tool_names": list(conn.allowed_remote_tool_names or []),
        "cached_remote_tools": list(conn.cached_remote_tools or []),
        "last_synced_at": (
            conn.last_synced_at.isoformat() if conn.last_synced_at else None
        ),
        "enabled": conn.enabled,
        "owner_type": "organization" if conn.organization_id else "user",
        "created_at": conn.created_at.isoformat(),
    }


def _sync_connection_tools(conn: MCPExternalConnection) -> tuple[bool, str | None]:
    try:
        tools = list_external_mcp_tools(
            connection_id=str(conn.id),
            command=conn.command,
            args=list(conn.args or []),
            env=dict(conn.env or {}),
            transport=conn.transport,
        )
    except Exception as exc:
        logger.exception("Failed to sync external MCP tools for %s", conn.id)
        return False, str(exc)
    conn.cached_remote_tools = tools
    conn.last_synced_at = timezone.now()
    conn.save(update_fields=["cached_remote_tools", "last_synced_at", "updated_at"])
    return True, None


@csrf_exempt
@token_required
@require_http_methods(["GET"])
def mcp_external_catalog(request):
    denied = _require_integrations_management(request)
    if denied:
        return denied
    entries = [catalog_entry_to_dict(e) for e in list_catalog_entries()]
    return JsonResponse({"catalog": entries})


@csrf_exempt
@token_required
@require_http_methods(["GET", "POST"])
def mcp_external_connections(request):
    denied = _require_integrations_management(request)
    if denied:
        return denied

    user = request.user

    if request.method == "GET":
        connections = _connections_visible_to_user(user)
        return JsonResponse(
            {"connections": [_connection_summary(c) for c in connections]}
        )

    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    catalog_key = (body.get("catalog_key") or "").strip()
    name = (body.get("name") or "").strip()
    if not catalog_key:
        return JsonResponse({"error": "catalog_key is required"}, status=400)
    if not name:
        return JsonResponse({"error": "name is required"}, status=400)

    entry = get_catalog_entry(catalog_key)
    if not entry:
        return JsonResponse({"error": f"Unknown catalog key: {catalog_key}"}, status=400)

    owner_user, owner_org, err = _connection_owner_for_create(user, body)
    if err:
        return err

    slug_raw = body.get("slug") or name
    slug = sanitize_connection_slug(slug_raw)

    allowed_slugs = body.get("allowed_agent_slugs") or []
    if allowed_slugs and not isinstance(allowed_slugs, list):
        return JsonResponse(
            {"error": "allowed_agent_slugs must be a list of slugs"},
            status=400,
        )

    conn = MCPExternalConnection(
        name=name,
        slug=slug,
        user=owner_user,
        organization=owner_org,
        catalog_key=entry.key,
        transport=entry.transport,
        command=entry.command,
        args=list(entry.args),
        env=dict(entry.env),
    )

    allowed_tools_raw = body.get("allowed_remote_tool_names")
    if allowed_tools_raw is not None and not isinstance(allowed_tools_raw, list):
        return JsonResponse(
            {"error": "allowed_remote_tool_names must be a list"},
            status=400,
        )

    try:
        conn.save()
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    if allowed_slugs:
        agents, agent_err = validate_agent_slugs_for_owner(
            user, owner_org, allowed_slugs
        )
        if agent_err:
            conn.delete()
            return JsonResponse({"error": agent_err}, status=400)
        conn.allowed_agents.set(agents)

    ok, sync_err = _sync_connection_tools(conn)
    if not ok:
        conn.delete()
        return JsonResponse(
            {"error": f"Could not connect to MCP server: {sync_err}"},
            status=502,
        )

    if allowed_tools_raw is not None:
        tool_names, tool_err = normalize_remote_tool_names(allowed_tools_raw, conn)
        if tool_err:
            conn.delete()
            return JsonResponse({"error": tool_err}, status=400)
        conn.allowed_remote_tool_names = tool_names or []
        conn.save(update_fields=["allowed_remote_tool_names", "updated_at"])

    conn.refresh_from_db()
    return JsonResponse(_connection_summary(conn), status=201)


@csrf_exempt
@token_required
@require_http_methods(["PATCH", "DELETE"])
def mcp_external_connection_detail(request, connection_id):
    denied = _require_integrations_management(request)
    if denied:
        return denied

    visible_ids = _connections_visible_to_user(request.user).values_list("id", flat=True)
    try:
        conn = MCPExternalConnection.objects.filter(id__in=visible_ids).get(
            id=connection_id
        )
    except MCPExternalConnection.DoesNotExist:
        return JsonResponse({"error": "Connection not found"}, status=404)

    if request.method == "DELETE":
        conn.revoked = True
        conn.enabled = False
        conn.save(update_fields=["revoked", "enabled", "updated_at"])
        return JsonResponse({"status": "revoked", "id": str(conn.id)})

    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    update_fields = ["updated_at"]

    if "name" in body:
        name = (body.get("name") or "").strip()
        if not name:
            return JsonResponse({"error": "name cannot be empty"}, status=400)
        conn.name = name
        update_fields.append("name")

    if "enabled" in body:
        conn.enabled = bool(body.get("enabled"))
        update_fields.append("enabled")

    if "allowed_agent_slugs" in body:
        slugs = body.get("allowed_agent_slugs") or []
        if not isinstance(slugs, list):
            return JsonResponse(
                {"error": "allowed_agent_slugs must be a list of slugs"},
                status=400,
            )
        org = conn.organization
        agents, agent_err = validate_agent_slugs_for_owner(
            request.user, org, slugs
        )
        if agent_err:
            return JsonResponse({"error": agent_err}, status=400)
        conn.allowed_agents.set(agents)

    if "allowed_remote_tool_names" in body:
        tool_names, tool_err = normalize_remote_tool_names(
            body.get("allowed_remote_tool_names"), conn
        )
        if tool_err:
            return JsonResponse({"error": tool_err}, status=400)
        conn.allowed_remote_tool_names = tool_names or []
        update_fields.append("allowed_remote_tool_names")

    conn.save(update_fields=update_fields)
    conn.refresh_from_db()
    return JsonResponse(_connection_summary(conn))


@csrf_exempt
@token_required
@require_http_methods(["POST"])
def mcp_external_connection_sync(request, connection_id):
    denied = _require_integrations_management(request)
    if denied:
        return denied

    visible_ids = _connections_visible_to_user(request.user).values_list("id", flat=True)
    try:
        conn = MCPExternalConnection.objects.filter(id__in=visible_ids).get(
            id=connection_id
        )
    except MCPExternalConnection.DoesNotExist:
        return JsonResponse({"error": "Connection not found"}, status=404)

    ok, sync_err = _sync_connection_tools(conn)
    if not ok:
        return JsonResponse(
            {"error": f"Sync failed: {sync_err}"},
            status=502,
        )
    conn.refresh_from_db()
    return JsonResponse(_connection_summary(conn))
