"""OAuth protected resource metadata (RFC 9728)."""

from __future__ import annotations

import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


def _frontend_url() -> str:
    return (os.getenv("FRONTEND_URL") or "").strip().rstrip("/")


@router.get("/.well-known/oauth-protected-resource")
async def oauth_protected_resource_metadata():
    issuer = _frontend_url()
    if not issuer:
        return JSONResponse(
            {"error": "FRONTEND_URL not configured"},
            status_code=503,
        )
    return {
        "resource": f"{issuer}/mcp",
        "authorization_servers": [issuer],
        "scopes_supported": ["mcp", "offline_access"],
        "bearer_methods_supported": ["header"],
    }
