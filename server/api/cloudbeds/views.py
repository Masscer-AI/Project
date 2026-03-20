"""
Views for the Cloudbeds OAuth integration.

Endpoints:
  GET  /v1/cloudbeds/connect/       → returns OAuth authorization URL
  GET  /v1/cloudbeds/callback/      → handles OAuth callback, stores credential, redirects to frontend
  GET  /v1/cloudbeds/status/        → returns connection status for the org
  POST /v1/cloudbeds/disconnect/    → deletes stored credential

OAuth flow:
  1. Frontend calls GET /connect/ (with auth token) → gets authorization_url.
  2. Frontend opens that URL (popup or redirect) — user grants access on Cloudbeds.
  3. Cloudbeds redirects browser to GET /callback/?code=...&state=...
  4. Backend exchanges code, stores CloudbedsCredential, redirects browser to
     CLOUDBEDS_FRONTEND_SUCCESS_URL (defaults to /settings/integrations).

The `state` param carries a short-lived cache key that maps back to the
requesting user's ID, so /callback/ knows which organization to associate
the credential with — without putting auth tokens in query strings.
"""

from __future__ import annotations

import json
import logging
import os
import secrets

from django.core.cache import cache
from django.http import HttpResponseRedirect, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from api.authenticate.decorators.token_required import token_required
from api.utils.cloudbeds import CloudBedsIntegration, CloudBedsError

logger = logging.getLogger(__name__)

# How long the state → user_id cache entry lives (seconds).
_STATE_TTL = 60 * 10  # 10 minutes

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_client_id() -> str:
    return os.environ.get("CLOUDBEDS_CLIENT_ID", "")


def _get_client_secret() -> str:
    return os.environ.get("CLOUDBEDS_CLIENT_SECRET", "")


def _get_redirect_uri(request) -> str:
    """
    The Cloudbeds callback URL registered in your app settings.
    Always points to the *backend* — this is where the code exchange happens.
    Override with CLOUDBEDS_REDIRECT_URI env var if needed (e.g. ngrok in dev).
    """
    override = os.environ.get("CLOUDBEDS_REDIRECT_URI", "")
    if override:
        return override
    return request.build_absolute_uri("/v1/cloudbeds/callback/")


def _get_frontend_success_url() -> str:
    """Frontend page to redirect the browser to after a successful connection."""
    base = os.environ.get("FRONTEND_URL", "").rstrip("/")
    return f"{base}/settings/integrations"


def _get_frontend_error_url(reason: str = "") -> str:
    """Frontend page to redirect to when the OAuth flow fails."""
    base = os.environ.get("FRONTEND_URL", "").rstrip("/")
    url = f"{base}/settings/integrations"
    return f"{url}?cloudbeds_error={reason}" if reason else url


def _get_org(user):
    """Return the Organization for a user, or None."""
    try:
        return user.profile.organization
    except Exception:
        return None


# ---------------------------------------------------------------------------
# /connect/ — return the Cloudbeds authorization URL
# ---------------------------------------------------------------------------

@csrf_exempt
@token_required
def cloudbeds_connect(request):
    """
    GET /v1/cloudbeds/connect/

    Returns the Cloudbeds OAuth authorization URL that the frontend should
    open (popup or redirect) to start the connection flow.

    The `state` value is a random token stored in Redis that maps back to
    the requesting user so /callback/ can identify the organization.

    Response:
        200 { "authorization_url": "https://hotels.cloudbeds.com/..." }
        400 { "error": "CLOUDBEDS_CLIENT_ID is not configured" }
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    client_id = _get_client_id()
    if not client_id:
        return JsonResponse({"error": "CLOUDBEDS_CLIENT_ID is not configured"}, status=400)

    # Store state → user_id in cache so /callback/ can look it up.
    state = secrets.token_urlsafe(24)
    cache.set(f"cloudbeds_oauth_state:{state}", request.user.id, timeout=_STATE_TTL)

    redirect_uri = _get_redirect_uri(request)
    authorization_url = CloudBedsIntegration.get_authorization_url(
        client_id=client_id,
        redirect_uri=redirect_uri,
        state=state,
    )

    return JsonResponse({
        "authorization_url": authorization_url,
        "state": state,
        "redirect_uri": redirect_uri,
    })


# ---------------------------------------------------------------------------
# /callback/ — handle the OAuth redirect from Cloudbeds
# ---------------------------------------------------------------------------

@csrf_exempt
def cloudbeds_callback(request):
    """
    GET /v1/cloudbeds/callback/?code=...&state=...&propertyID=...

    Handles the Cloudbeds OAuth redirect:
      1. Validates the state param against the Redis cache entry set in /connect/.
      2. Exchanges the authorization code for tokens.
      3. Fetches property metadata.
      4. Persists a CloudbedsCredential for the user's organization.
      5. Redirects the browser to CLOUDBEDS_FRONTEND_SUCCESS_URL.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    code = request.GET.get("code", "")
    state = request.GET.get("state", "")
    error = request.GET.get("error", "")
    property_id = request.GET.get("propertyID", "")

    if error:
        logger.warning("Cloudbeds OAuth error: %s", error)
        return HttpResponseRedirect(_get_frontend_error_url(error))

    if not code:
        return HttpResponseRedirect(_get_frontend_error_url("missing_code"))

    # Recover the user from the state cache entry.
    user_id = cache.get(f"cloudbeds_oauth_state:{state}") if state else None
    if not user_id:
        logger.warning("Cloudbeds callback: invalid or expired state '%s'", state)
        return HttpResponseRedirect(_get_frontend_error_url("invalid_state"))

    # Consume state (one-time use).
    cache.delete(f"cloudbeds_oauth_state:{state}")

    from django.contrib.auth.models import User

    try:
        user = User.objects.select_related("profile__organization").get(id=user_id)
    except User.DoesNotExist:
        return HttpResponseRedirect(_get_frontend_error_url("user_not_found"))

    org = _get_org(user)
    if not org:
        return HttpResponseRedirect(_get_frontend_error_url("no_organization"))

    client_id = _get_client_id()
    client_secret = _get_client_secret()
    if not client_id or not client_secret:
        return HttpResponseRedirect(_get_frontend_error_url("server_misconfigured"))

    # Exchange code for tokens.
    try:
        token_data = CloudBedsIntegration.exchange_code_for_token(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=_get_redirect_uri(request),
            code=code,
        )
    except CloudBedsError as exc:
        logger.error("Cloudbeds token exchange failed: %s", exc)
        return HttpResponseRedirect(_get_frontend_error_url("token_exchange_failed"))

    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token", "")
    expires_in = token_data.get("expires_in")
    expires_at = (
        timezone.now() + timezone.timedelta(seconds=int(expires_in))
        if expires_in
        else None
    )

    # Fetch property metadata with the new token.
    property_name = ""
    try:
        cb = CloudBedsIntegration(access_token=access_token)
        userinfo = cb.get_property_info()
        data = userinfo.get("data", {}) if isinstance(userinfo, dict) else {}
        property_name = data.get("propertyName", "") or userinfo.get("propertyName", "")
        if not property_id:
            property_id = str(data.get("propertyID", "") or userinfo.get("propertyID", ""))
    except Exception as exc:
        logger.warning("Could not fetch property info after token exchange: %s", exc)

    # Persist the credential.
    from api.cloudbeds.models import CloudbedsCredential

    CloudbedsCredential.objects.update_or_create(
        organization=org,
        defaults={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
            "property_id": property_id,
            "property_name": property_name,
        },
    )
    logger.info(
        "Cloudbeds connected: org=%s property=%s (%s)",
        org.id, property_id, property_name,
    )

    return HttpResponseRedirect(_get_frontend_success_url())


# ---------------------------------------------------------------------------
# /save/ — persist tokens from callback into the DB
# ---------------------------------------------------------------------------

@csrf_exempt
@token_required
def cloudbeds_save(request):
    """
    POST /v1/cloudbeds/save/

    Body (JSON):
        {
            "access_token":  "...",
            "refresh_token": "...",        (optional)
            "expires_at":    "2026-...",   (optional ISO datetime)
            "property_id":   "12345",      (optional)
            "property_name": "My Hotel"    (optional)
        }

    Saves or updates the CloudbedsCredential for the user's organization.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    org = _get_org(request.user)
    if not org:
        return JsonResponse({"error": "User has no organization"}, status=400)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    access_token = body.get("access_token", "").strip()
    if not access_token:
        return JsonResponse({"error": "access_token is required"}, status=400)

    refresh_token = body.get("refresh_token", "")
    property_id = body.get("property_id", "")
    property_name = body.get("property_name", "")

    expires_at = None
    raw_expires = body.get("expires_at")
    if raw_expires:
        from django.utils.dateparse import parse_datetime
        expires_at = parse_datetime(raw_expires)

    from api.cloudbeds.models import CloudbedsCredential

    credential, created = CloudbedsCredential.objects.update_or_create(
        organization=org,
        defaults={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
            "property_id": property_id,
            "property_name": property_name,
        },
    )

    return JsonResponse({
        "success": True,
        "created": created,
        "property_id": credential.property_id,
        "property_name": credential.property_name,
    })


# ---------------------------------------------------------------------------
# /status/ — check if connected
# ---------------------------------------------------------------------------

@csrf_exempt
@token_required
def cloudbeds_status(request):
    """
    GET /v1/cloudbeds/status/

    Returns the connection status for the user's organization.

    Response:
        { "connected": true,  "property_id": "...", "property_name": "..." }
        { "connected": false }
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    org = _get_org(request.user)
    if not org:
        return JsonResponse({"connected": False, "reason": "no_organization"})

    from api.cloudbeds.models import CloudbedsCredential

    try:
        cred = CloudbedsCredential.objects.get(organization=org)
        return JsonResponse({
            "connected": True,
            "property_id": cred.property_id,
            "property_name": cred.property_name,
            "expires_at": cred.expires_at.isoformat() if cred.expires_at else None,
            "is_expired": cred.is_expired,
        })
    except CloudbedsCredential.DoesNotExist:
        return JsonResponse({"connected": False})


# ---------------------------------------------------------------------------
# /disconnect/ — remove the stored credential
# ---------------------------------------------------------------------------

@csrf_exempt
@token_required
def cloudbeds_disconnect(request):
    """
    POST /v1/cloudbeds/disconnect/

    Removes the Cloudbeds credential for the user's organization,
    effectively disconnecting the integration.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    org = _get_org(request.user)
    if not org:
        return JsonResponse({"error": "User has no organization"}, status=400)

    from api.cloudbeds.models import CloudbedsCredential

    deleted, _ = CloudbedsCredential.objects.filter(organization=org).delete()
    return JsonResponse({
        "success": True,
        "disconnected": deleted > 0,
    })
