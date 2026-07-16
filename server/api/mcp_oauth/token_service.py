"""OAuth token issuance and validation."""

from __future__ import annotations

import base64
import uuid
from datetime import timedelta

from authlib.oauth2.rfc7636.challenge import compare_s256_code_challenge
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from api.mcp_oauth.crypto import generate_token, hash_secret, verify_secret
from api.mcp_oauth.models import (
    OAuthAccessToken,
    OAuthAuthorizationCode,
    OAuthClient,
    OAuthRefreshToken,
)
from api.mcp_oauth.settings_helpers import resource_matches


def _access_ttl() -> timedelta:
    sec = int(getattr(settings, "MCP_OAUTH_ACCESS_TOKEN_TTL", 3600))
    return timedelta(seconds=sec)


def _refresh_ttl() -> timedelta:
    sec = int(getattr(settings, "MCP_OAUTH_REFRESH_TOKEN_TTL", 60 * 60 * 24 * 30))
    return timedelta(seconds=sec)


def _auth_code_ttl() -> timedelta:
    sec = int(getattr(settings, "MCP_OAUTH_AUTH_CODE_TTL", 60))
    return timedelta(seconds=sec)


def authenticate_client(
    client: OAuthClient,
    client_secret: str | None,
    auth_method_used: str | None,
) -> bool:
    if client.disabled:
        return False
    method = client.token_endpoint_auth_method
    if method == OAuthClient.AUTH_NONE:
        return True
    if not client_secret:
        return False
    return verify_secret(client_secret, client.client_secret_hash)


def extract_client_credentials(request) -> tuple[str | None, str | None, str | None]:
    """Return (client_id, client_secret, auth_method)."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("basic "):
        try:
            decoded = base64.b64decode(auth_header[6:].strip()).decode("utf-8")
            client_id, client_secret = decoded.split(":", 1)
            return client_id, client_secret, OAuthClient.AUTH_SECRET_BASIC
        except Exception:
            return None, None, OAuthClient.AUTH_SECRET_BASIC
    client_id = request.POST.get("client_id")
    client_secret = request.POST.get("client_secret")
    if client_secret:
        return client_id, client_secret, OAuthClient.AUTH_SECRET_POST
    return client_id, client_secret, OAuthClient.AUTH_NONE


def mint_authorization_code(
    *,
    client: OAuthClient,
    user,
    mcp_client,
    redirect_uri: str,
    code_challenge: str,
    scope: str,
    resource: str,
) -> str:
    raw_code = generate_token(32)
    OAuthAuthorizationCode.objects.create(
        code_hash=hash_secret(raw_code),
        client=client,
        user=user,
        mcp_client=mcp_client,
        redirect_uri=redirect_uri,
        code_challenge=code_challenge,
        scope=scope,
        resource=resource,
        expires_at=timezone.now() + _auth_code_ttl(),
    )
    return raw_code


def exchange_authorization_code(
    *,
    client: OAuthClient,
    code: str,
    redirect_uri: str,
    code_verifier: str,
    resource: str | None,
) -> tuple[str, str, int] | tuple[None, str]:
    code_hash = hash_secret(code)
    try:
        auth_code = OAuthAuthorizationCode.objects.select_related(
            "user", "mcp_client", "client"
        ).get(code_hash=code_hash, client=client)
    except OAuthAuthorizationCode.DoesNotExist:
        return None, "invalid_grant"

    if auth_code.is_consumed() or auth_code.is_expired():
        return None, "invalid_grant"
    if auth_code.redirect_uri != redirect_uri:
        return None, "invalid_grant"
    if resource and not resource_matches(resource):
        return None, "invalid_grant"
    if resource and auth_code.resource.rstrip("/") != resource.rstrip("/"):
        return None, "invalid_grant"
    if not compare_s256_code_challenge(code_verifier, auth_code.code_challenge):
        return None, "invalid_grant"
    if auth_code.mcp_client.revoked:
        return None, "invalid_grant"

    auth_code.consumed_at = timezone.now()
    auth_code.save(update_fields=["consumed_at"])

    access_raw, refresh_raw, expires_in = _issue_tokens(
        client=client,
        user=auth_code.user,
        mcp_client=auth_code.mcp_client,
        scope=auth_code.scope,
        resource=auth_code.resource,
        family_id=uuid.uuid4(),
    )
    return access_raw, refresh_raw, expires_in


def refresh_access_token(
    *,
    client: OAuthClient,
    refresh_token: str,
    resource: str | None,
) -> tuple[str, str, int] | tuple[None, str]:
    token_hash = hash_secret(refresh_token)
    try:
        old_refresh = OAuthRefreshToken.objects.select_related(
            "user", "mcp_client", "client"
        ).get(token_hash=token_hash, client=client)
    except OAuthRefreshToken.DoesNotExist:
        return None, "invalid_grant"

    if old_refresh.revoked:
        _revoke_refresh_family(old_refresh.family_id)
        return None, "invalid_grant"

    if old_refresh.rotated_at is not None:
        _revoke_refresh_family(old_refresh.family_id)
        return None, "invalid_grant"

    if old_refresh.is_expired():
        return None, "invalid_grant"

    if resource and not resource_matches(resource):
        return None, "invalid_grant"
    if resource and old_refresh.resource.rstrip("/") != resource.rstrip("/"):
        return None, "invalid_grant"
    if old_refresh.mcp_client.revoked:
        return None, "invalid_grant"

    with transaction.atomic():
        old_refresh.rotated_at = timezone.now()
        old_refresh.save(update_fields=["rotated_at"])
        OAuthAccessToken.objects.filter(
            mcp_client=old_refresh.mcp_client,
            client=client,
            revoked=False,
        ).update(revoked=True)

        access_raw, refresh_raw, expires_in = _issue_tokens(
            client=client,
            user=old_refresh.user,
            mcp_client=old_refresh.mcp_client,
            scope=old_refresh.scope,
            resource=old_refresh.resource,
            family_id=old_refresh.family_id,
        )
    return access_raw, refresh_raw, expires_in


def _issue_tokens(
    *,
    client: OAuthClient,
    user,
    mcp_client,
    scope: str,
    resource: str,
    family_id: uuid.UUID,
) -> tuple[str, str, int]:
    access_raw = generate_token(48)
    refresh_raw = generate_token(48)
    expires_at = timezone.now() + _access_ttl()
    OAuthAccessToken.objects.create(
        token_hash=hash_secret(access_raw),
        client=client,
        user=user,
        mcp_client=mcp_client,
        scope=scope,
        resource=resource,
        expires_at=expires_at,
    )
    OAuthRefreshToken.objects.create(
        token_hash=hash_secret(refresh_raw),
        family_id=family_id,
        client=client,
        user=user,
        mcp_client=mcp_client,
        scope=scope,
        resource=resource,
        expires_at=timezone.now() + _refresh_ttl(),
    )
    expires_in = int((expires_at - timezone.now()).total_seconds())
    return access_raw, refresh_raw, expires_in


def _revoke_refresh_family(family_id: uuid.UUID) -> None:
    OAuthRefreshToken.objects.filter(family_id=family_id).update(revoked=True)
    OAuthAccessToken.objects.filter(
        mcp_client__oauth_refresh_tokens__family_id=family_id,
        revoked=False,
    ).update(revoked=True)


def resolve_access_token(raw_token: str) -> OAuthAccessToken | None:
    if not raw_token:
        return None
    token = (
        OAuthAccessToken.objects.filter(
            token_hash=hash_secret(raw_token),
            revoked=False,
        )
        .select_related("mcp_client", "user", "client")
        .first()
    )
    if not token or not token.is_active():
        return None
    if token.mcp_client.revoked:
        return None
    return token


def introspect_token(raw_token: str) -> dict:
    from api.ai_layers.models import MCPClient

    if not raw_token:
        return {"active": False}

    oauth_token = resolve_access_token(raw_token)
    if oauth_token:
        return {
            "active": True,
            "mcp_client_id": str(oauth_token.mcp_client_id),
            "scope": oauth_token.scope,
            "sub": str(oauth_token.user_id),
            "exp": int(oauth_token.expires_at.timestamp()),
            "client_id": oauth_token.client.client_id,
            "token_type": "oauth",
        }

    mcp_client = MCPClient.get_valid(raw_token)
    if mcp_client:
        return {
            "active": True,
            "mcp_client_id": str(mcp_client.id),
            "scope": "mcp",
            "sub": str(mcp_client.user_id),
            "exp": None,
            "client_id": None,
            "token_type": "legacy",
        }
    return {"active": False}
