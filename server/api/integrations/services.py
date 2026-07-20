"""
Helpers for integration OAuth flows and token management.
"""

from __future__ import annotations

import os
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from django.contrib.auth.models import User
from django.utils import timezone

from api.authenticate.models import Organization
from api.authenticate.services import FeatureFlagService
from api.authenticate.subdomain_utils import (
    get_frontend_base_url,
    is_allowed_return_to_host,
)

from .models import Integration, IntegrationProvider as IntegrationProviderChoices
from .providers import IntegrationProviderError, get_provider

OwnerType = Literal["user", "organization"]
VALID_OWNERS: frozenset[str] = frozenset({"user", "organization"})
VALID_PROVIDERS: frozenset[str] = frozenset({c.value for c in IntegrationProviderChoices})

INTEGRATIONS_MANAGE_FEATURE_FLAG = "can-manage-integrations"
INTEGRATIONS_RETURN_PATH_PREFIX = "/integrations"

# google_calendar is personal-only (no organization-owned connection).
USER_ONLY_INTEGRATION_PROVIDERS: frozenset[str] = frozenset(
    {IntegrationProviderChoices.GOOGLE_CALENDAR.value}
)


def reject_user_only_provider_org_owner(provider: str, owner_type: str) -> None:
    if provider in USER_ONLY_INTEGRATION_PROVIDERS and owner_type == "organization":
        raise ValueError(
            f"{provider} can only be connected for your personal account, not the organization."
        )


def user_has_personal_google_calendar(user_id: int | None) -> bool:
    if not user_id:
        return False
    from .models import Integration, IntegrationStatus

    return Integration.objects.filter(
        user_id=user_id,
        provider=IntegrationProviderChoices.GOOGLE_CALENDAR,
        status=IntegrationStatus.ACTIVE,
    ).exists()


def get_google_client_id() -> str:
    return os.environ.get("GOOGLE_CLIENT_ID", "").strip()


def get_google_client_secret() -> str:
    return os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()


def get_redirect_uri(request, provider: str) -> str:
    """Backend callback URL for OAuth redirect (canonical, not tenant host)."""
    env_key = f"{provider.upper()}_REDIRECT_URI"
    override = os.environ.get(env_key, "").strip()
    if override:
        return override
    generic = os.environ.get("GOOGLE_DRIVE_REDIRECT_URI", "").strip()
    if generic:
        return generic
    frontend_base = get_frontend_base_url()
    if frontend_base:
        return f"{frontend_base}/v1/integrations/{provider}/callback/"
    return request.build_absolute_uri(f"/v1/integrations/{provider}/callback/")


def get_frontend_integrations_url(*, error: str = "") -> str:
    base = get_frontend_base_url()
    url = f"{base}{INTEGRATIONS_RETURN_PATH_PREFIX}"
    if error:
        return f"{url}?error={error}"
    return url


def validate_return_to(url: str) -> str | None:
    """Return normalized return URL or None if unsafe."""
    raw = (url or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        return None
    if not is_allowed_return_to_host(parsed.hostname or ""):
        return None
    path = parsed.path or ""
    if not path.startswith(INTEGRATIONS_RETURN_PATH_PREFIX):
        return None
    normalized = urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            path.rstrip("/") or INTEGRATIONS_RETURN_PATH_PREFIX,
            "",
            "",
            "",
        )
    )
    return normalized


def resolve_integrations_return_to(raw: str | None) -> str:
    validated = validate_return_to(raw or "")
    if validated:
        return validated
    return get_frontend_integrations_url()


def build_integrations_return_url(return_to: str, *, error: str = "") -> str:
    base_url = resolve_integrations_return_to(return_to)
    if not error:
        return base_url
    parsed = urlparse(base_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["error"] = error
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(query),
            parsed.fragment,
        )
    )


def get_user_organization(user: User) -> Organization | None:
    owned = Organization.objects.filter(owner=user).first()
    if owned:
        return owned
    profile = getattr(user, "profile", None)
    if profile and profile.organization_id:
        return profile.organization
    return None


def integrations_capability_denied_message() -> str:
    return (
        f"The '{INTEGRATIONS_MANAGE_FEATURE_FLAG}' feature is not enabled "
        "for your account."
    )


def user_can_manage_integrations(user: User, organization: Organization | None) -> bool:
    enabled, _ = FeatureFlagService.is_feature_enabled(
        INTEGRATIONS_MANAGE_FEATURE_FLAG,
        organization=organization,
        user=user,
    )
    return enabled


def parse_owner_type(raw: str | None, default: str = "user") -> OwnerType:
    value = (raw or default).strip().lower()
    if value not in VALID_OWNERS:
        raise ValueError(f"owner must be one of: {', '.join(sorted(VALID_OWNERS))}")
    return value  # type: ignore[return-value]


def validate_provider_key(provider: str) -> str:
    key = (provider or "").strip().lower()
    if key not in VALID_PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    return key


def integration_queryset_for_user(user: User):
    org = get_user_organization(user)
    from django.db.models import Q

    q = Q(user=user)
    if org:
        q |= Q(organization=org)
    return Integration.objects.filter(q).select_related("user", "organization")


def get_integration_for_owner(
    *,
    provider: str,
    owner_type: OwnerType,
    user: User,
    organization: Organization | None,
) -> Integration | None:
    if owner_type == "user":
        return Integration.objects.filter(provider=provider, user=user).first()
    if organization is None:
        return None
    return Integration.objects.filter(provider=provider, organization=organization).first()


def ensure_valid_access_token(integration: Integration) -> str:
    """
    Return a valid access token, refreshing and persisting if expired.
    """
    if not integration.is_expired:
        return integration.access_token

    if not integration.refresh_token:
        raise IntegrationProviderError("Access token expired and no refresh token is available.")

    provider = get_provider(
        integration.provider,
        client_id=get_google_client_id(),
        client_secret=get_google_client_secret(),
        redirect_uri="",  # not needed for refresh
    )
    token_data = provider.refresh_access_token(integration.refresh_token)
    integration.access_token = token_data["access_token"]
    if token_data.get("refresh_token"):
        integration.refresh_token = token_data["refresh_token"]
    expires_in = token_data.get("expires_in")
    integration.expires_at = (
        timezone.now() + timezone.timedelta(seconds=int(expires_in))
        if expires_in
        else None
    )
    integration.save(
        update_fields=["access_token", "refresh_token", "expires_at", "updated_at"]
    )
    return integration.access_token


def serialize_integration(integration: Integration) -> dict:
    return {
        "id": integration.id,
        "provider": integration.provider,
        "owner_type": integration.owner_type,
        "owner_label": integration.owner_label,
        "account_email": integration.account_email,
        "account_label": integration.account_label,
        "status": integration.status,
        "scopes": integration.scopes,
        "metadata": integration.metadata,
        "expires_at": integration.expires_at.isoformat() if integration.expires_at else None,
        "is_expired": integration.is_expired,
        "connected": integration.status == "active",
        "created_at": integration.created_at.isoformat(),
        "updated_at": integration.updated_at.isoformat(),
    }
