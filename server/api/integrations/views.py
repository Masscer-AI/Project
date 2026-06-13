"""
Views for third-party integrations (Google Drive, future providers).

Endpoints:
  GET  /v1/integrations/                              → list caller's integrations
  GET  /v1/integrations/<provider>/connect/?owner=    → OAuth authorization URL
  GET  /v1/integrations/<provider>/callback/          → OAuth callback
  POST /v1/integrations/<provider>/disconnect/        → remove integration
"""

from __future__ import annotations

import json
import logging
import secrets

from django.core.cache import cache
from django.http import HttpResponseRedirect, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from api.authenticate.decorators.token_required import token_required
from api.authenticate.services import FeatureFlagService

from .models import Integration, IntegrationStatus
from .providers import IntegrationProviderError, get_provider
from .services import (
    ensure_valid_access_token,
    get_frontend_integrations_url,
    get_google_client_id,
    get_google_client_secret,
    get_integration_for_owner,
    get_redirect_uri,
    get_user_organization,
    integration_queryset_for_user,
    parse_owner_type,
    serialize_integration,
    user_can_manage_integrations,
    validate_provider_key,
)

logger = logging.getLogger(__name__)

_STATE_TTL = 60 * 10  # 10 minutes
_STATE_CACHE_PREFIX = "integrations_oauth_state:"


def _method_not_allowed(request):
    return JsonResponse({"error": "Method not allowed"}, status=405)


def _json_body(request) -> dict:
    try:
        return json.loads(request.body) if request.body else {}
    except (json.JSONDecodeError, ValueError):
        return {}


def _require_capability(request, owner_type: str):
    org = get_user_organization(request.user)
    if not user_can_manage_integrations(request.user, org):
        return JsonResponse(
            {
                "error": (
                    "The 'can-connect-drive-account' feature is not enabled "
                    "for your account."
                )
            },
            status=403,
        )
    if owner_type == "organization" and org is None:
        return JsonResponse(
            {"error": "User has no organization to connect for."},
            status=400,
        )
    return None


@csrf_exempt
@token_required
def integrations_list(request):
    """GET /v1/integrations/ — list personal and organization integrations."""
    if request.method != "GET":
        return _method_not_allowed(request)

    integrations = integration_queryset_for_user(request.user).order_by("-updated_at")
    return JsonResponse(
        {"integrations": [serialize_integration(i) for i in integrations]}
    )


@csrf_exempt
@token_required
def integrations_connect(request, provider: str):
    """
    GET /v1/integrations/<provider>/connect/?owner=user|organization

    Returns the OAuth authorization URL.
    """
    if request.method != "GET":
        return _method_not_allowed(request)

    try:
        provider_key = validate_provider_key(provider)
        owner_type = parse_owner_type(request.GET.get("owner"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    err = _require_capability(request, owner_type)
    if err:
        return err

    client_id = get_google_client_id()
    if not client_id:
        return JsonResponse({"error": "GOOGLE_CLIENT_ID is not configured"}, status=400)

    state = secrets.token_urlsafe(24)
    cache.set(
        f"{_STATE_CACHE_PREFIX}{state}",
        {
            "user_id": request.user.id,
            "provider": provider_key,
            "owner_type": owner_type,
        },
        timeout=_STATE_TTL,
    )

    redirect_uri = get_redirect_uri(request, provider_key)
    provider_instance = get_provider(
        provider_key,
        client_id=client_id,
        client_secret=get_google_client_secret(),
        redirect_uri=redirect_uri,
    )
    authorization_url = provider_instance.get_authorization_url(state)

    return JsonResponse(
        {
            "authorization_url": authorization_url,
            "state": state,
            "redirect_uri": redirect_uri,
            "owner_type": owner_type,
            "provider": provider_key,
        }
    )


@csrf_exempt
def integrations_callback(request, provider: str):
    """
    GET /v1/integrations/<provider>/callback/?code=...&state=...

    Handles OAuth redirect, stores Integration, redirects to frontend.
    """
    if request.method != "GET":
        return _method_not_allowed(request)

    try:
        provider_key = validate_provider_key(provider)
    except ValueError:
        return HttpResponseRedirect(get_frontend_integrations_url(error="unknown_provider"))

    code = request.GET.get("code", "")
    state = request.GET.get("state", "")
    oauth_error = request.GET.get("error", "")

    if oauth_error:
        logger.warning("Integration OAuth error (%s): %s", provider_key, oauth_error)
        return HttpResponseRedirect(get_frontend_integrations_url(error=oauth_error))

    if not code:
        return HttpResponseRedirect(get_frontend_integrations_url(error="missing_code"))

    state_data = cache.get(f"{_STATE_CACHE_PREFIX}{state}") if state else None
    if not state_data:
        logger.error(
            "Integration callback: invalid or expired state '%s'. "
            "This usually means the Redis cache entry expired, the state was "
            "already consumed, or the cache backend is not shared between the "
            "connect and callback requests.",
            state,
        )
        return HttpResponseRedirect(get_frontend_integrations_url(error="invalid_state"))

    cache.delete(f"{_STATE_CACHE_PREFIX}{state}")

    if state_data.get("provider") != provider_key:
        return HttpResponseRedirect(get_frontend_integrations_url(error="provider_mismatch"))

    from django.contrib.auth.models import User

    try:
        user = User.objects.select_related("profile__organization").get(
            id=state_data["user_id"]
        )
    except User.DoesNotExist:
        return HttpResponseRedirect(get_frontend_integrations_url(error="user_not_found"))

    owner_type = state_data.get("owner_type", "user")
    org = get_user_organization(user)

    if owner_type == "organization" and org is None:
        return HttpResponseRedirect(get_frontend_integrations_url(error="no_organization"))

    enabled, _ = FeatureFlagService.is_feature_enabled(
        "can-connect-drive-account",
        organization=org,
        user=user,
    )
    if not enabled:
        return HttpResponseRedirect(get_frontend_integrations_url(error="access_denied"))

    client_id = get_google_client_id()
    client_secret = get_google_client_secret()
    if not client_id or not client_secret:
        return HttpResponseRedirect(get_frontend_integrations_url(error="server_misconfigured"))

    redirect_uri = get_redirect_uri(request, provider_key)
    provider_instance = get_provider(
        provider_key,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )

    try:
        token_data = provider_instance.exchange_code_for_token(code)
        access_token = token_data["access_token"]
        account_info = provider_instance.fetch_account_info(access_token)
    except IntegrationProviderError as exc:
        logger.error("Integration token exchange failed: %s", exc)
        return HttpResponseRedirect(get_frontend_integrations_url(error="token_exchange_failed"))

    refresh_token = token_data.get("refresh_token", "")
    expires_in = token_data.get("expires_in")
    expires_at = (
        timezone.now() + timezone.timedelta(seconds=int(expires_in))
        if expires_in
        else None
    )
    scope_raw = token_data.get("scope", "")
    scopes = scope_raw if isinstance(scope_raw, str) else " ".join(scope_raw or [])

    metadata = provider_instance.build_metadata_from_token_response(token_data, account_info)
    account_email = account_info.get("email", "") or metadata.get("account_email", "") or ""
    account_label = account_info.get("name", "") or account_email

    defaults: dict = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
        "scopes": scopes,
        "account_email": account_email,
        "account_label": account_label,
        "metadata": metadata,
        "status": IntegrationStatus.ACTIVE,
    }

    try:
        if owner_type == "user":
            integration, created = Integration.objects.update_or_create(
                user=user,
                provider=provider_key,
                defaults={**defaults, "organization": None},
            )
        else:
            integration, created = Integration.objects.update_or_create(
                organization=org,
                provider=provider_key,
                defaults={**defaults, "user": None},
            )
        logger.info(
            "Integration %s: provider=%s owner_type=%s id=%s",
            "created" if created else "updated",
            provider_key,
            owner_type,
            integration.id,
        )
    except Exception as exc:
        logger.error(
            "Integration save failed: provider=%s owner_type=%s error=%s",
            provider_key,
            owner_type,
            exc,
            exc_info=True,
        )
        return HttpResponseRedirect(get_frontend_integrations_url(error="save_failed"))

    return HttpResponseRedirect(get_frontend_integrations_url())


@csrf_exempt
@token_required
def integrations_disconnect(request, provider: str):
    """
    POST /v1/integrations/<provider>/disconnect/

    Body: { "owner": "user" | "organization" }
    """
    if request.method != "POST":
        return _method_not_allowed(request)

    try:
        provider_key = validate_provider_key(provider)
        body = _json_body(request)
        owner_type = parse_owner_type(body.get("owner"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    err = _require_capability(request, owner_type)
    if err:
        return err

    org = get_user_organization(request.user)
    integration = get_integration_for_owner(
        provider=provider_key,
        owner_type=owner_type,
        user=request.user,
        organization=org,
    )

    if integration is None:
        return JsonResponse({"success": True, "disconnected": False})

    deleted, _ = Integration.objects.filter(pk=integration.pk).delete()
    return JsonResponse({"success": True, "disconnected": deleted > 0})
