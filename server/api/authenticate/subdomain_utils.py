"""Helpers for organization tenant subdomains."""

from __future__ import annotations

import re

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


def get_base_domain() -> str:
    return getattr(settings, "BASE_DOMAIN", "masscer.ai").strip().lower() or "masscer.ai"


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

    base_domain = get_base_domain()
    suffix = f".{base_domain}"
    if hostname == base_domain or not hostname.endswith(suffix):
        return None

    label = hostname[: -len(suffix)]
    if label.count(".") != 0:
        return None
    if not label or label in RESERVED_SUBDOMAINS:
        return None
    return label
