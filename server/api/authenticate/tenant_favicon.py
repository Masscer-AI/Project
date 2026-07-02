"""Generate tenant favicon from organization logo."""

from __future__ import annotations

import os
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image

from .models import Organization, OrganizationTenant


def organization_tenant_favicon_upload_path(instance: OrganizationTenant, filename: str) -> str:
    ext = filename.split(".")[-1] if "." in filename else "png"
    return os.path.join("organizations", "tenants", "favicons", f"{instance.organization_id}.{ext}")


def clear_tenant_favicon(tenant: OrganizationTenant) -> None:
    if tenant.favicon:
        try:
            if tenant.favicon.path and os.path.exists(tenant.favicon.path):
                os.remove(tenant.favicon.path)
        except (ValueError, OSError):
            pass
        tenant.favicon = None
        tenant.save(update_fields=["favicon", "updated_at"])


def regenerate_tenant_favicon_from_logo(organization: Organization) -> None:
    """Resize org logo to 32x32 PNG and store on OrganizationTenant.favicon."""
    try:
        tenant = organization.tenant
    except OrganizationTenant.DoesNotExist:
        return

    if not organization.logo:
        clear_tenant_favicon(tenant)
        return

    try:
        with organization.logo.open("rb") as logo_file:
            image = Image.open(logo_file)
            image = image.convert("RGBA")
            image.thumbnail((32, 32), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            buffer.seek(0)
    except (OSError, ValueError):
        return

    if tenant.favicon:
        try:
            if tenant.favicon.path and os.path.exists(tenant.favicon.path):
                os.remove(tenant.favicon.path)
        except (ValueError, OSError):
            pass

    filename = f"{organization.id}.png"
    tenant.favicon.save(filename, ContentFile(buffer.read()), save=True)
