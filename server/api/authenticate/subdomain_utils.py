"""Helpers for organization tenant subdomains."""

from __future__ import annotations

import os
import re
from urllib.parse import urlparse, urlunparse

from django.conf import settings
from django.core.exceptions import ValidationError

RESERVED_SUBDOMAINS = frozenset(
    {
        "app",
        "core",
        "www",
        "api",
        "admin",
        "static",
        "media",
        "mail",
        "ftp",
        "localhost",
    }
)

_SUBDOMAIN_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


# Fallback tenant base domain when FRONTEND_URL is not set (e.g. management commands).
DEFAULT_TENANT_BASE_DOMAIN = "masscer.ai"


def normalize_subdomain(value: str) -> str:
    return (value or "").strip().lower()


def validate_subdomain(value: str) -> str:
    """Return normalized subdomain or raise ValidationError."""
    subdomain = normalize_subdomain(value)
    if not subdomain:
        raise ValidationError("Subdomain is required.")
    if len(subdomain) > 63:
        raise ValidationError("Subdomain must be at most 63 characters.")
    if not _SUBDOMAIN_RE.match(subdomain):
        raise ValidationError(
            "Subdomain must use lowercase letters, numbers, and hyphens only, "
            "and cannot start or end with a hyphen."
        )
    if subdomain in RESERVED_SUBDOMAINS:
        raise ValidationError("This subdomain is reserved.")
    return subdomain


def extract_subdomain(host: str) -> str | None:
    """
    Extract tenant subdomain label from Host header.

    Examples:
      acme.masscer.ai -> acme
      acme.localhost -> acme
      app.masscer.ai -> None (reserved)
      masscer.ai -> None
      localhost -> None
    """
    if not host:
        return None

    hostname = host.split(":", 1)[0].strip().lower().rstrip(".")
    if not hostname or hostname in {"localhost", "127.0.0.1"}:
        return None

    if hostname.endswith(".localhost"):
        label = hostname[: -len(".localhost")]
        if label.count(".") == 0 and label and label not in RESERVED_SUBDOMAINS:
            return label
        return None

    base_domain = get_tenant_base_domain()
    suffix = f".{base_domain}"
    if hostname == base_domain or not hostname.endswith(suffix):
        return None

    label = hostname[: -len(suffix)]
    if label.count(".") != 0:
        return None
    if not label or label in RESERVED_SUBDOMAINS:
        return None
    return label


def get_tenant_base_domain() -> str:
    """
    Hostname suffix for tenant portals: acme.{return value}.

    Derived from FRONTEND_URL when set (localhost, app.masscer.ai, tunnels),
    else DEFAULT_TENANT_BASE_DOMAIN.
    """
    frontend = get_frontend_base_url()
    if frontend:
        host = (urlparse(frontend).hostname or "").lower()
        if host in {"localhost", "127.0.0.1"}:
            return "localhost"
        if host.startswith("app.") and len(host) > len("app."):
            return host[len("app.") :]
        if host:
            return host
    return DEFAULT_TENANT_BASE_DOMAIN


def get_tenant_label(hostname: str) -> str | None:
    """Return tenant subdomain label if host is a tenant portal, else None."""
    if not hostname:
        return None

    host = hostname.split(":", 1)[0].strip().lower().rstrip(".")
    if not host or host in {"localhost", "127.0.0.1"}:
        return None

    if host.endswith(".localhost"):
        label = host[: -len(".localhost")]
        if label.count(".") == 0 and label and label not in RESERVED_SUBDOMAINS:
            return label
        return None

    if host.startswith("app."):
        return None

    tenant_base = get_tenant_base_domain()
    if tenant_base == "localhost":
        return None

    suffix = f".{tenant_base}"
    if not host.endswith(suffix):
        return None
    label = host[: -len(suffix)]
    if label.count(".") != 0 or not label or label in RESERVED_SUBDOMAINS:
        return None
    return label


def build_tenant_portal_host(subdomain: str) -> str:
    return f"{subdomain}.{get_tenant_base_domain()}"


def get_frontend_base_url() -> str:
    return (
        getattr(settings, "FRONTEND_URL", None) or os.environ.get("FRONTEND_URL", "")
    ).strip().rstrip("/")


def is_allowed_return_to_host(hostname: str) -> bool:
    if not hostname:
        return False
    host = hostname.lower()
    if host in {"localhost", "127.0.0.1"}:
        return True
    if extract_subdomain(host):
        return True
    frontend_base = get_frontend_base_url()
    if frontend_base:
        frontend_host = urlparse(frontend_base).hostname
        if frontend_host and frontend_host.lower() == host:
            return True
    tenant_base = get_tenant_base_domain()
    if tenant_base != "localhost" and host in {tenant_base, f"app.{tenant_base}"}:
        return True
    return False


def validate_auth_return_to_origin(url: str) -> str | None:
    """Return normalized origin (scheme + netloc) or None if unsafe."""
    raw = (url or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        return None
    if not is_allowed_return_to_host(parsed.hostname or ""):
        return None
    if parsed.path not in {"", "/"}:
        return None
    if parsed.params or parsed.query or parsed.fragment:
        return None
    return urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))


def validate_google_auth_redirect_uri(url: str) -> str | None:
    """Return normalized redirect URI for GIS auth-code flow or None if unsafe."""
    raw = (url or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        return None
    origin = validate_auth_return_to_origin(f"{parsed.scheme}://{parsed.netloc}")
    if not origin:
        return None
    hostname = urlparse(origin).hostname or ""
    if extract_subdomain(hostname):
        return None
    path = (parsed.path or "").rstrip("/") or "/"
    if path != "/auth/google":
        return None
    if parsed.params or parsed.query or parsed.fragment:
        return None
    return urlunparse((parsed.scheme, parsed.netloc, "/auth/google", "", "", ""))
