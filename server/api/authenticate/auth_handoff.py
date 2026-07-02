"""One-time auth handoff codes for cross-origin Google Sign-In."""

from __future__ import annotations

import secrets

from django.contrib.auth.models import User
from django.core.cache import cache

from .models import Token

HANDOFF_TTL_SECONDS = 60
_CACHE_PREFIX = "auth_handoff:"


def create_handoff_code(user_id: int, return_to_origin: str) -> str:
    code = secrets.token_urlsafe(32)
    cache.set(
        f"{_CACHE_PREFIX}{code}",
        {"user_id": user_id, "return_to": return_to_origin},
        timeout=HANDOFF_TTL_SECONDS,
    )
    return code


def exchange_handoff_code(code: str) -> tuple[User, str] | None:
    if not code or not code.strip():
        return None
    key = f"{_CACHE_PREFIX}{code.strip()}"
    data = cache.get(key)
    if not data:
        return None
    cache.delete(key)
    try:
        user = User.objects.get(pk=data["user_id"])
    except User.DoesNotExist:
        return None
    return user, data.get("return_to", "")


def issue_login_token_for_handoff(user: User) -> Token:
    token, _ = Token.get_or_create(user=user, token_type="login")
    return token
