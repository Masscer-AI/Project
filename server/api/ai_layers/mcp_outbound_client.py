"""HTTP client for the FastAPI internal MCP outbound proxy."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SEC = float(os.getenv("MCP_OUTBOUND_TIMEOUT_SEC", "30"))


def _base_url() -> str:
    return (
        getattr(settings, "FASTAPI_INTERNAL_URL", None)
        or os.getenv("FASTAPI_INTERNAL_URL")
        or os.getenv("STREAMING_SERVER_URL")
        or "http://localhost:8001"
    ).rstrip("/")


def _headers() -> dict[str, str]:
    token = getattr(settings, "INTERNAL_MCP_PROXY_TOKEN", None) or os.getenv(
        "INTERNAL_MCP_PROXY_TOKEN", ""
    )
    if not token:
        raise RuntimeError("INTERNAL_MCP_PROXY_TOKEN is not configured")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _post(path: str, payload: dict) -> dict:
    url = f"{_base_url()}{path}"
    resp = requests.post(
        url,
        headers=_headers(),
        json=payload,
        timeout=DEFAULT_TIMEOUT_SEC,
    )
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail") or resp.json().get("error")
        except Exception:
            detail = resp.text
        raise RuntimeError(detail or f"MCP proxy error ({resp.status_code})")
    return resp.json()


def list_external_mcp_tools(
    *,
    connection_id: str,
    command: str,
    args: list[str] | None = None,
    env: dict | None = None,
    transport: str = "stdio",
) -> list[dict]:
    data = _post(
        "/internal/mcp/list-tools",
        {
            "connection_id": connection_id,
            "transport": transport,
            "command": command,
            "args": args or [],
            "env": env or {},
        },
    )
    tools = data.get("tools") or []
    return tools if isinstance(tools, list) else []


def call_external_mcp_tool(
    *,
    connection_id: str,
    command: str,
    args: list[str] | None = None,
    env: dict | None = None,
    transport: str = "stdio",
    tool_name: str,
    arguments: dict | None = None,
) -> str:
    data = _post(
        "/internal/mcp/call",
        {
            "connection_id": connection_id,
            "transport": transport,
            "command": command,
            "args": args or [],
            "env": env or {},
            "tool_name": tool_name,
            "arguments": arguments or {},
        },
    )
    output = data.get("output", "")
    if isinstance(output, str):
        return output
    return json.dumps(output, ensure_ascii=False)
