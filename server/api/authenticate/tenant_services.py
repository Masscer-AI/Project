"""Shared helpers for organization tenant portal config."""

from __future__ import annotations

from api.authenticate.models import Organization, OrganizationTenant, Token
from api.authenticate.subdomain_utils import build_tenant_portal_host
from api.authenticate.tenant_schemas import tenant_theme_for_response


def get_user_organization(user) -> Organization | None:
    """Resolve the user's primary organization (owned org, else member org)."""
    if not user:
        return None
    owned_org = Organization.objects.filter(owner=user).first()
    if owned_org:
        return owned_org
    profile = getattr(user, "profile", None)
    if profile and profile.organization_id:
        return profile.organization
    return None


def user_from_optional_auth_header(request) -> object | None:
    """Return the authenticated user from Authorization header, or None."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    try:
        _token_type, token_key = auth_header.split(" ", 1)
    except ValueError:
        return None
    token = Token.get_valid(token_key)
    if not token:
        return None
    user = token.user
    profile = getattr(user, "profile", None)
    if profile and profile.organization_id and not profile.is_active:
        return None
    return user


def get_tenant_for_organization(organization: Organization) -> OrganizationTenant | None:
    try:
        return organization.tenant
    except OrganizationTenant.DoesNotExist:
        return None


def get_or_create_tenant(organization: Organization) -> OrganizationTenant:
    tenant, _ = OrganizationTenant.objects.get_or_create(organization=organization)
    return tenant


def build_public_tenant_config(tenant: OrganizationTenant, request) -> dict:
    organization = tenant.organization
    logo_url = organization.logo.url if organization.logo else None
    favicon_url = tenant.favicon.url if tenant.favicon else logo_url
    app_name = (tenant.app_name or "").strip() or organization.name

    return {
        "subdomain": tenant.subdomain,
        "portal_host": build_tenant_portal_host(tenant.subdomain) if tenant.subdomain else None,
        "app_name": app_name,
        "logo_url": logo_url,
        "favicon_url": favicon_url,
        "subdomain": tenant.subdomain,
        "theme": tenant_theme_for_response(tenant.theme),
        "hide_powered_by": tenant.hide_powered_by,
    }


def serialize_tenant_for_manage(tenant: OrganizationTenant, request) -> dict:
    organization = tenant.organization
    favicon_url = tenant.favicon.url if tenant.favicon else None
    if not favicon_url and organization.logo:
        favicon_url = organization.logo.url

    return {
        "subdomain": tenant.subdomain,
        "portal_host": build_tenant_portal_host(tenant.subdomain) if tenant.subdomain else None,
        "app_name": tenant.app_name,
        "theme": tenant_theme_for_response(tenant.theme),
        "hide_powered_by": tenant.hide_powered_by,
        "favicon_url": favicon_url,
        "logo_url": organization.logo.url if organization.logo else None,
    }
