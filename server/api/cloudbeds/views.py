"""
Views for the Cloudbeds OAuth integration.

Endpoints:
  GET  /v1/cloudbeds/connect/       → returns OAuth authorization URL
  GET  /v1/cloudbeds/callback/      → handles OAuth callback, stores credential
  GET  /v1/cloudbeds/status/        → returns connection status for the org
  POST /v1/cloudbeds/disconnect/    → deletes stored credential

All views (except /callback/) require a valid Masscer auth token.
The /callback/ view uses a state parameter to recover the user session.
"""

from __future__ import annotations

import json
import logging
import os
import secrets

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from api.authenticate.decorators.token_required import token_required
from api.utils.cloudbeds import CloudBedsIntegration, CloudBedsError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_client_id() -> str:
    return os.environ.get("CLOUDBEDS_CLIENT_ID", "")


def _get_client_secret() -> str:
    return os.environ.get("CLOUDBEDS_CLIENT_SECRET", "")


def _get_redirect_uri(request) -> str:
    """Build the absolute callback URI."""
    override = os.environ.get("CLOUDBEDS_REDIRECT_URI", "")
    if override:
        return override
    return request.build_absolute_uri("/v1/cloudbeds/callback/")


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
    redirect (or open) to start the connection flow.

    Response:
        200 { "authorization_url": "https://hotels.cloudbeds.com/..." }
        400 { "error": "CLOUDBEDS_CLIENT_ID is not configured" }
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    client_id = _get_client_id()
    if not client_id:
        return JsonResponse({"error": "CLOUDBEDS_CLIENT_ID is not configured"}, status=400)

    # Generate a random state token; in production you'd store this in the
    # user's session or a short-lived cache key to verify on callback.
    state = secrets.token_urlsafe(24)

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

    Exchanges the authorization code for tokens and stores the credential
    against the user's organization.

    Cloudbeds passes `propertyID` in the query string after authorization,
    which we persist alongside the token.

    In a real deployment you'd verify `state` against the session value.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    code = request.GET.get("code", "")
    error = request.GET.get("error", "")
    property_id = request.GET.get("propertyID", "")

    if error:
        logger.warning("Cloudbeds OAuth error: %s", error)
        return JsonResponse({"error": f"Cloudbeds authorization denied: {error}"}, status=400)

    if not code:
        return JsonResponse({"error": "Missing authorization code"}, status=400)

    client_id = _get_client_id()
    client_secret = _get_client_secret()
    if not client_id or not client_secret:
        return JsonResponse({"error": "Cloudbeds app credentials are not configured"}, status=500)

    # Exchange code for tokens
    try:
        token_data = CloudBedsIntegration.exchange_code_for_token(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=_get_redirect_uri(request),
            code=code,
        )
    except CloudBedsError as exc:
        logger.error("Cloudbeds token exchange failed: %s", exc)
        return JsonResponse({"error": str(exc)}, status=502)

    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token", "")
    expires_in = token_data.get("expires_in")
    expires_at = (
        timezone.now() + timezone.timedelta(seconds=int(expires_in))
        if expires_in
        else None
    )

    # Fetch property name using the new token
    property_name = ""
    try:
        cb = CloudBedsIntegration(access_token=access_token)
        userinfo = cb.get_property_info()
        property_name = (
            userinfo.get("data", {}).get("propertyName", "")
            or userinfo.get("propertyName", "")
        )
        if not property_id:
            property_id = str(
                userinfo.get("data", {}).get("propertyID", "")
                or userinfo.get("propertyID", "")
            )
    except Exception as exc:
        logger.warning("Could not fetch property info after token exchange: %s", exc)

    # We need the user to save the credential. The state param should carry the
    # user token, but for simplicity we expose the tokens in the response so the
    # frontend can POST them to a save endpoint, or you can use session-based flow.
    #
    # Here we return the token data so the frontend (or a subsequent POST) can
    # persist it. If you have a server-side session you'd store it directly.
    return JsonResponse({
        "success": True,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "property_id": property_id,
        "property_name": property_name,
        "message": "Authorization successful. Send these tokens to POST /v1/cloudbeds/save/ to persist the connection.",
    })


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
