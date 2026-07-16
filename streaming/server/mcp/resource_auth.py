"""ASGI auth wrapper for MCP resource server (401 + introspection)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any

import httpx
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from server.mcp.auth import extract_bearer_from_scope, set_mcp_bearer_token

logger = logging.getLogger(__name__)

_INTROSPECT_CACHE: dict[str, tuple[bool, float]] = {}
_CACHE_TTL_SEC = float(os.getenv("MCP_INTROSPECT_CACHE_TTL_SEC", "30"))


def _frontend_url() -> str:
    return (os.getenv("FRONTEND_URL") or "").strip().rstrip("/")


def _api_url() -> str:
    return (
        os.getenv("API_URL")
        or os.getenv("STREAMING_SERVER_URL")
        or "http://localhost:8000"
    ).rstrip("/")


def _introspect_token(token: str) -> bool:
    import time

    cache_key = hashlib.sha256(token.encode()).hexdigest()
    now = time.time()
    cached = _INTROSPECT_CACHE.get(cache_key)
    if cached and cached[1] > now:
        return cached[0]

    secret = os.getenv("INTERNAL_MCP_INTROSPECT_TOKEN", "")
    if not secret:
        logger.warning("INTERNAL_MCP_INTROSPECT_TOKEN not configured")
        return False

    url = f"{_api_url()}/v1/mcp_oauth/introspect/"
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(
                url,
                headers={
                    "Authorization": f"Bearer {secret}",
                    "Content-Type": "application/json",
                },
                json={"token": token},
            )
        if resp.status_code != 200:
            active = False
        else:
            data = resp.json()
            active = bool(data.get("active"))
    except Exception:
        logger.exception("Token introspection failed")
        active = False

    _INTROSPECT_CACHE[cache_key] = (active, now + _CACHE_TTL_SEC)
    return active


async def _send_401(send: Send) -> None:
    issuer = _frontend_url()
    metadata_url = (
        f"{issuer}/.well-known/oauth-protected-resource" if issuer else ""
    )
    www_auth = (
        f'Bearer resource_metadata="{metadata_url}", error="invalid_token"'
        if metadata_url
        else 'Bearer error="invalid_token"'
    )
    body = json.dumps({"error": "invalid_token"}).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"www-authenticate", www_auth.encode("latin-1")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class MCPResourceAuthMiddleware:
    """Validate bearer tokens before handing off to Streamable HTTP MCP handler."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET").upper()
        if method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        token = extract_bearer_from_scope(scope)
        if not token or not _introspect_token(token):
            await _send_401(send)
            return

        set_mcp_bearer_token(token)
        try:
            await self.app(scope, receive, send)
        finally:
            set_mcp_bearer_token(None)


def wrap_mcp_app(app: ASGIApp) -> ASGIApp:
    return MCPResourceAuthMiddleware(app)
