"""Bearer token extraction for MCP requests."""

from __future__ import annotations

from contextvars import ContextVar

_mcp_bearer_token: ContextVar[str | None] = ContextVar("mcp_bearer_token", default=None)


def set_mcp_bearer_token(token: str | None) -> None:
    _mcp_bearer_token.set(token)


def get_mcp_bearer_token() -> str | None:
    return _mcp_bearer_token.get()


def extract_bearer_from_scope(scope: dict) -> str | None:
    headers = dict(scope.get("headers") or [])
    auth = headers.get(b"authorization", b"").decode("latin-1")
    if not auth.lower().startswith("bearer "):
        return None
    token = auth[7:].strip()
    return token or None
