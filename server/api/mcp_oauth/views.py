"""OAuth 2.1 HTTP endpoints and consent API."""

from __future__ import annotations

import json
import logging
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from api.ai_layers.mcp_access import normalize_mcp_tool_names
from api.ai_layers.models import MCPClient
from api.authenticate.decorators.token_required import token_required
from api.integrations.services import get_user_organization, user_can_manage_integrations
from api.mcp_oauth.cimd import resolve_cimd_client
from api.mcp_oauth.crypto import generate_client_id, generate_token, hash_secret
from api.mcp_oauth.models import OAuthAuthorizationRequest, OAuthClient
from api.mcp_oauth.settings_helpers import mcp_resource_id, oauth_issuer, resource_matches
from api.mcp_oauth.token_service import (
    authenticate_client,
    exchange_authorization_code,
    extract_client_credentials,
    mint_authorization_code,
    refresh_access_token,
)

logger = logging.getLogger(__name__)


def _oauth_error(error: str, description: str = "", status: int = 400) -> JsonResponse:
    payload = {"error": error}
    if description:
        payload["error_description"] = description
    return JsonResponse(payload, status=status)


def _require_introspect_token(request) -> bool:
    expected = getattr(settings, "INTERNAL_MCP_INTROSPECT_TOKEN", "") or ""
    if not expected:
        return False
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        return secrets.compare_digest(token, expected)
    return False


def _resolve_client(client_id: str) -> OAuthClient | None:
    if not client_id:
        return None
    client = OAuthClient.objects.filter(client_id=client_id, disabled=False).first()
    if client:
        return client
    if client_id.startswith("https://"):
        return resolve_cimd_client(client_id)
    return None


def _validate_redirect_uri(client: OAuthClient, redirect_uri: str) -> bool:
    return redirect_uri in (client.redirect_uris or [])


def _consent_url(request_id: str) -> str:
    issuer = oauth_issuer()
    return f"{issuer}/oauth/consent?req={request_id}"


@require_http_methods(["GET"])
def authorization_server_metadata(request):
    issuer = oauth_issuer()
    if not issuer:
        return JsonResponse({"error": "FRONTEND_URL not configured"}, status=503)
    return JsonResponse(
        {
            "issuer": issuer,
            "authorization_endpoint": f"{issuer}/oauth/authorize",
            "token_endpoint": f"{issuer}/oauth/token",
            "registration_endpoint": f"{issuer}/oauth/register",
            "scopes_supported": ["mcp", "offline_access"],
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": [
                "client_secret_basic",
                "client_secret_post",
                "none",
            ],
            "client_id_metadata_document_supported": True,
        }
    )


@csrf_exempt
@require_http_methods(["GET"])
def oauth_authorize(request):
    client_id = (request.GET.get("client_id") or "").strip()
    redirect_uri = (request.GET.get("redirect_uri") or "").strip()
    response_type = (request.GET.get("response_type") or "").strip()
    state = request.GET.get("state") or ""
    scope = (request.GET.get("scope") or "mcp offline_access").strip()
    resource = (request.GET.get("resource") or "").strip()
    code_challenge = (request.GET.get("code_challenge") or "").strip()
    code_challenge_method = (request.GET.get("code_challenge_method") or "").strip()

    if response_type != "code":
        return _oauth_error("unsupported_response_type", status=400)
    if code_challenge_method and code_challenge_method != "S256":
        return _oauth_error("invalid_request", "Only S256 PKCE is supported")
    if not code_challenge:
        return _oauth_error("invalid_request", "code_challenge is required")
    if not resource_matches(resource):
        return _oauth_error("invalid_target", "Invalid resource parameter")

    client = _resolve_client(client_id)
    if not client:
        return _oauth_error("invalid_client", status=401)
    if not _validate_redirect_uri(client, redirect_uri):
        return _oauth_error("invalid_request", "Invalid redirect_uri")

    auth_req = OAuthAuthorizationRequest.objects.create(
        client=client,
        redirect_uri=redirect_uri,
        state=state,
        code_challenge=code_challenge,
        code_challenge_method="S256",
        scope=scope,
        resource=resource or mcp_resource_id(),
        expires_at=timezone.now() + timedelta(minutes=10),
    )
    return redirect(_consent_url(str(auth_req.id)))


@csrf_exempt
@require_http_methods(["POST"])
def oauth_token(request):
    grant_type = (request.POST.get("grant_type") or "").strip()
    client_id, client_secret, auth_method = extract_client_credentials(request)
    client = _resolve_client(client_id or "")
    if not client:
        return _oauth_error("invalid_client", status=401)
    if not authenticate_client(client, client_secret, auth_method):
        return _oauth_error("invalid_client", status=401)

    if grant_type == "authorization_code":
        code = (request.POST.get("code") or "").strip()
        redirect_uri = (request.POST.get("redirect_uri") or "").strip()
        code_verifier = (request.POST.get("code_verifier") or "").strip()
        resource = (request.POST.get("resource") or "").strip() or None
        if not code or not redirect_uri or not code_verifier:
            return _oauth_error("invalid_request")
        result = exchange_authorization_code(
            client=client,
            code=code,
            redirect_uri=redirect_uri,
            code_verifier=code_verifier,
            resource=resource,
        )
        if result[0] is None:
            return _oauth_error(result[1], status=400)
        access_token, refresh_token, expires_in = result
        payload = {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": expires_in,
            "refresh_token": refresh_token,
            "scope": request.POST.get("scope") or "mcp offline_access",
        }
        return JsonResponse(payload)

    if grant_type == "refresh_token":
        refresh_token = (request.POST.get("refresh_token") or "").strip()
        resource = (request.POST.get("resource") or "").strip() or None
        if not refresh_token:
            return _oauth_error("invalid_request")
        result = refresh_access_token(
            client=client,
            refresh_token=refresh_token,
            resource=resource,
        )
        if result[0] is None:
            return _oauth_error(result[1], status=400)
        access_token, new_refresh, expires_in = result
        return JsonResponse(
            {
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": expires_in,
                "refresh_token": new_refresh,
                "scope": request.POST.get("scope") or "mcp offline_access",
            }
        )

    return _oauth_error("unsupported_grant_type")


@csrf_exempt
@require_http_methods(["POST"])
def oauth_register(request):
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return _oauth_error("invalid_client_metadata", status=400)

    redirect_uris = body.get("redirect_uris") or []
    if not isinstance(redirect_uris, list) or not redirect_uris:
        return _oauth_error("invalid_client_metadata", "redirect_uris required")
    client_name = (body.get("client_name") or "MCP Client").strip()[:255]
    token_auth = body.get("token_endpoint_auth_method") or "none"
    if token_auth not in ("none", "client_secret_basic", "client_secret_post"):
        token_auth = "none"

    secret = None
    secret_hash = ""
    if token_auth != "none":
        secret = generate_token(32)
        secret_hash = hash_secret(secret)

    client = OAuthClient.objects.create(
        client_id=generate_client_id(),
        client_secret_hash=secret_hash,
        client_name=client_name,
        redirect_uris=redirect_uris,
        token_endpoint_auth_method=token_auth,
        grant_types=["authorization_code", "refresh_token"],
        registration_source=OAuthClient.REGISTRATION_DCR,
    )
    payload = {
        "client_id": client.client_id,
        "client_name": client.client_name,
        "redirect_uris": client.redirect_uris,
        "grant_types": client.grant_types,
        "token_endpoint_auth_method": client.token_endpoint_auth_method,
        "client_id_issued_at": int(client.created_at.timestamp()),
    }
    if secret:
        payload["client_secret"] = secret
    return JsonResponse(payload, status=201)


def _require_integrations_management(request):
    org = get_user_organization(request.user)
    if not user_can_manage_integrations(request.user, org):
        return JsonResponse(
            {"error": "can-manage-integrations feature required"},
            status=403,
        )
    return None


def _conversational_agents(user):
    from api.ai_layers.access import accessible_agents_qs
    from api.ai_layers.models import AgentKind

    return accessible_agents_qs(user).filter(
        agent_kind=AgentKind.CONVERSATIONAL_AGENT
    )


@csrf_exempt
@token_required
@require_http_methods(["GET"])
def authorize_request_detail(request, request_id):
    try:
        auth_req = OAuthAuthorizationRequest.objects.select_related("client").get(
            id=request_id
        )
    except OAuthAuthorizationRequest.DoesNotExist:
        return JsonResponse({"error": "Authorization request not found"}, status=404)
    if auth_req.is_expired():
        return JsonResponse({"error": "Authorization request expired"}, status=410)

    agents = [
        {"slug": a.slug, "name": a.name}
        for a in _conversational_agents(request.user)
    ]
    from api.ai_layers.mcp_access import mcp_tool_preset_groups

    tool_presets = mcp_tool_preset_groups()
    return JsonResponse(
        {
            "id": str(auth_req.id),
            "client_name": auth_req.client.client_name,
            "client_id": auth_req.client.client_id,
            "scope": auth_req.scope,
            "resource": auth_req.resource,
            "redirect_uri": auth_req.redirect_uri,
            "state": auth_req.state,
            "agents": agents,
            "tool_presets": tool_presets,
        }
    )


@csrf_exempt
@token_required
@require_http_methods(["POST"])
def authorize_request_approve(request, request_id):
    try:
        auth_req = OAuthAuthorizationRequest.objects.select_related("client").get(
            id=request_id
        )
    except OAuthAuthorizationRequest.DoesNotExist:
        return JsonResponse({"error": "Authorization request not found"}, status=404)
    if auth_req.is_expired():
        return JsonResponse({"error": "Authorization request expired"}, status=410)

    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    credential_name = (body.get("credential_name") or auth_req.client.client_name).strip()
    allowed_slugs = body.get("allowed_agent_slugs") or []
    allowed_tools_raw = body.get("allowed_tool_names")

    org = get_user_organization(request.user)
    mcp_client = MCPClient.objects.create(
        name=credential_name[:255],
        user=request.user,
        organization=org,
        scopes=[s for s in auth_req.scope.split() if s],
    )

    if allowed_slugs:
        agents = list(_conversational_agents(request.user))
        slug_set = {a.slug for a in agents}
        invalid = [s for s in allowed_slugs if s not in slug_set]
        if invalid:
            mcp_client.delete()
            return JsonResponse(
                {"error": f"Agent(s) not accessible: {', '.join(invalid)}"},
                status=400,
            )
        mcp_client.allowed_agents.set([a for a in agents if a.slug in allowed_slugs])

    if allowed_tools_raw is not None:
        tool_names, tool_err = normalize_mcp_tool_names(allowed_tools_raw)
        if tool_err:
            mcp_client.delete()
            return JsonResponse({"error": tool_err}, status=400)
        mcp_client.allowed_tool_names = tool_names or []
        mcp_client.save(update_fields=["allowed_tool_names", "updated_at"])

    auth_req.user = request.user
    auth_req.save(update_fields=["user"])

    code = mint_authorization_code(
        client=auth_req.client,
        user=request.user,
        mcp_client=mcp_client,
        redirect_uri=auth_req.redirect_uri,
        code_challenge=auth_req.code_challenge,
        scope=auth_req.scope,
        resource=auth_req.resource,
    )
    params = {"code": code}
    if auth_req.state:
        params["state"] = auth_req.state
    redirect_url = f"{auth_req.redirect_uri}?{urlencode(params)}"
    return JsonResponse({"redirect_url": redirect_url})


@csrf_exempt
@token_required
@require_http_methods(["POST"])
def authorize_request_deny(request, request_id):
    try:
        auth_req = OAuthAuthorizationRequest.objects.get(id=request_id)
    except OAuthAuthorizationRequest.DoesNotExist:
        return JsonResponse({"error": "Authorization request not found"}, status=404)
    params = {"error": "access_denied"}
    if auth_req.state:
        params["state"] = auth_req.state
    redirect_url = f"{auth_req.redirect_uri}?{urlencode(params)}"
    return JsonResponse({"redirect_url": redirect_url})


@csrf_exempt
@require_http_methods(["POST"])
def token_introspect(request):
    if not _require_introspect_token(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    from api.mcp_oauth.token_service import introspect_token

    token = (body.get("token") or "").strip()
    return JsonResponse(introspect_token(token))


@csrf_exempt
@token_required
@require_http_methods(["GET", "POST"])
def oauth_clients(request):
    denied = _require_integrations_management(request)
    if denied:
        return denied
    user = request.user
    org = get_user_organization(user)

    if request.method == "GET":
        qs = OAuthClient.objects.filter(
            owner_user=user,
            registration_source=OAuthClient.REGISTRATION_MANUAL,
            disabled=False,
        )
        return JsonResponse(
            {
                "mcp_url": mcp_resource_id(),
                "clients": [
                    {
                        "id": str(c.id),
                        "client_id": c.client_id,
                        "client_name": c.client_name,
                        "redirect_uris": c.redirect_uris,
                        "token_endpoint_auth_method": c.token_endpoint_auth_method,
                        "created_at": c.created_at.isoformat(),
                    }
                    for c in qs
                ]
            }
        )

    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    name = (body.get("client_name") or "").strip()
    redirect_uris = body.get("redirect_uris") or []
    confidential = body.get("confidential", True)
    if not name:
        return JsonResponse({"error": "client_name is required"}, status=400)
    if not isinstance(redirect_uris, list) or not redirect_uris:
        return JsonResponse({"error": "redirect_uris is required"}, status=400)

    client, secret = OAuthClient.create_manual(
        client_name=name,
        redirect_uris=redirect_uris,
        owner_user=user,
        organization=org,
        confidential=bool(confidential),
    )
    payload = {
        "id": str(client.id),
        "client_id": client.client_id,
        "client_name": client.client_name,
        "redirect_uris": client.redirect_uris,
        "token_endpoint_auth_method": client.token_endpoint_auth_method,
        "mcp_url": mcp_resource_id(),
    }
    if secret:
        payload["client_secret"] = secret
    return JsonResponse(payload, status=201)


@csrf_exempt
@token_required
@require_http_methods(["DELETE"])
def oauth_client_detail(request, client_id):
    denied = _require_integrations_management(request)
    if denied:
        return denied
    try:
        client = OAuthClient.objects.get(
            id=client_id,
            owner_user=request.user,
            registration_source=OAuthClient.REGISTRATION_MANUAL,
        )
    except OAuthClient.DoesNotExist:
        return JsonResponse({"error": "Client not found"}, status=404)
    client.disabled = True
    client.save(update_fields=["disabled", "updated_at"])
    return JsonResponse({"status": "revoked", "id": str(client.id)})
