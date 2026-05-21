"""Download WhatsApp Cloud API media (Graph + CDN URL)."""

from __future__ import annotations

from urllib.parse import urlparse

import requests
from django.conf import settings

_GRAPH_API_BASE = "https://graph.facebook.com/v21.0"
# Hosts Meta returns for media download URLs (see Darwin security-app WhatsappService).
_WHATSAPP_MEDIA_HOST_SUFFIXES = ("fbsbx.com", "fbcdn.net", "facebook.com")


def _allowed_media_host(host: str) -> bool:
    host = (host or "").lower()
    return any(
        host == s or host.endswith(f".{s}") for s in _WHATSAPP_MEDIA_HOST_SUFFIXES
    )


def fetch_whatsapp_media_bytes(
    media_id: str, *, direct_url: str | None = None
) -> tuple[bytes, str]:
    """
    Fetch media bytes. If ``direct_url`` is omitted, resolves URL via Graph ``/{media_id}``.
    """
    token = (getattr(settings, "WHATSAPP_GRAPH_API_TOKEN", None) or "").strip()
    if not token:
        raise RuntimeError("WHATSAPP_GRAPH_API_TOKEN is not configured")
    headers = {"Authorization": f"Bearer {token}"}
    url = direct_url
    if not url:
        meta = requests.get(
            f"{_GRAPH_API_BASE}/{media_id}",
            headers=headers,
            timeout=30,
        )
        meta.raise_for_status()
        url = meta.json().get("url") or ""
    host = urlparse(url).hostname or ""
    if not _allowed_media_host(host):
        raise ValueError(f"WhatsApp media URL has unexpected host: {host!r}")
    download = requests.get(url, headers=headers, timeout=120)
    download.raise_for_status()
    mime = (download.headers.get("Content-Type") or "application/octet-stream").split(
        ";"
    )[0].strip()
    return download.content, mime
