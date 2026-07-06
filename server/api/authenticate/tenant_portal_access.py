"""Access control for organization tenant portals (subdomain hosts)."""

from __future__ import annotations

from urllib.parse import urlparse

from rest_framework import status
from rest_framework.response import Response

from api.authenticate.models import Organization, OrganizationTenant
from api.authenticate.subdomain_utils import (
    extract_subdomain,
    get_frontend_base_url,
    get_tenant_base_domain,
    validate_auth_return_to_origin,
)
from api.document_templates.access import user_belongs_to_organization

WRONG_ORGANIZATION_PORTAL_CODE = "wrong_organization_portal"
TENANT_PORTAL_SIGNUP_FORBIDDEN_CODE = "tenant_portal_signup_forbidden"


def get_portal_origin_from_data(data: dict) -> str | None:
    raw = (data.get("portal_origin") or data.get("return_to") or "").strip()
    if not raw:
        return None
    return validate_auth_return_to_origin(raw)


def resolve_tenant_organization_from_portal_origin(
    portal_origin: str | None,
) -> Organization | None:
    if not portal_origin:
        return None
    hostname = urlparse(portal_origin).hostname or ""
    subdomain = extract_subdomain(hostname)
    if not subdomain:
        return None
    try:
        tenant = OrganizationTenant.objects.select_related("organization").get(
            subdomain=subdomain
        )
    except OrganizationTenant.DoesNotExist:
        return None
    return tenant.organization


def build_canonical_app_login_url() -> str:
    frontend_base = get_frontend_base_url()
    if frontend_base:
        return f"{frontend_base.rstrip('/')}/login"
    tenant_base = get_tenant_base_domain()
    if tenant_base == "localhost":
        return "http://localhost/login"
    return f"https://app.{tenant_base}/login"


def wrong_organization_portal_response() -> Response:
    return Response(
        {
            "error": (
                "You don't have access to this organization portal. "
                "Use the main application to sign in with your account."
            ),
            "code": WRONG_ORGANIZATION_PORTAL_CODE,
            "redirect_to": build_canonical_app_login_url(),
        },
        status=status.HTTP_403_FORBIDDEN,
    )


def tenant_portal_open_signup_denied_response() -> Response:
    return Response(
        {
            "error": (
                "Open signup is not available on organization portals. "
                "Contact your organization administrator for an invite."
            ),
            "code": TENANT_PORTAL_SIGNUP_FORBIDDEN_CODE,
            "redirect_to": build_canonical_app_login_url(),
        },
        status=status.HTTP_403_FORBIDDEN,
    )


def check_user_tenant_portal_access(user, portal_origin: str | None) -> Response | None:
    tenant_org = resolve_tenant_organization_from_portal_origin(portal_origin)
    if tenant_org is None:
        return None
    if not user_belongs_to_organization(user, tenant_org):
        return wrong_organization_portal_response()
    return None


def check_tenant_portal_signup_allowed(
    data: dict,
    *,
    invite_organization_id=None,
) -> Response | None:
    portal_origin = get_portal_origin_from_data(data)
    tenant_org = resolve_tenant_organization_from_portal_origin(portal_origin)
    if tenant_org is None:
        return None

    if invite_organization_id is not None:
        if invite_organization_id != tenant_org.id:
            return wrong_organization_portal_response()
        return None

    if data.get("organization_name"):
        return tenant_portal_open_signup_denied_response()

    org_id = data.get("organization_id")
    if org_id and str(org_id) != str(tenant_org.id):
        return wrong_organization_portal_response()

    if not org_id:
        return tenant_portal_open_signup_denied_response()

    return None
