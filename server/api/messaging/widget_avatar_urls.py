"""Absolute URLs for ChatWidget avatar files (admin UI and public embed config)."""

from __future__ import annotations

from django.conf import settings

from .models import ChatWidget


def resolved_avatar_image(widget: ChatWidget) -> str:
    """
    Public URL for the widget avatar: uploaded file takes precedence over avatar_image text.
    """
    file_field = getattr(widget, "avatar", None)
    if file_field:
        url = file_field.url
        if url:
            if isinstance(url, str) and url.startswith("http"):
                return url
            api_base = (getattr(settings, "API_BASE_URL", None) or "").strip().rstrip("/")
            if api_base and isinstance(url, str):
                path = url if url.startswith("/") else f"/{url}"
                return f"{api_base}{path}"
            if isinstance(url, str) and url.startswith("https"):
                return url

    text = (widget.avatar_image or "").strip()
    return text


def clear_widget_uploaded_avatar(widget: ChatWidget) -> None:
    """Remove stored avatar file and clear the ImageField (does not save)."""
    if widget.avatar:
        widget.avatar.delete(save=False)
        widget.avatar = None
