"""Absolute URLs for MessageAttachment files (UI, tools, WhatsApp outbound)."""

from __future__ import annotations

from django.conf import settings

from .models import MessageAttachment


def absolute_file_url_for_attachment(att: MessageAttachment) -> str | None:
    """
    Public HTTPS URL when possible (S3 MEDIA_URL or API_BASE_URL + /media/ path).
    Returns None if the attachment has no file.
    """
    file_field = getattr(att, "file", None)
    if not file_field:
        return None
    url = file_field.url
    if not url:
        return None
    if isinstance(url, str) and url.startswith("http"):
        return url
    api_base = (getattr(settings, "API_BASE_URL", None) or "").strip().rstrip("/")
    if api_base and isinstance(url, str):
        path = url if url.startswith("/") else f"/{url}"
        return f"{api_base}{path}"
    return url if isinstance(url, str) and url.startswith("https") else None
