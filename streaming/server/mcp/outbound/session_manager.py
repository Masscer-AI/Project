"""Manage persistent stdio MCP client sessions keyed by connection_id."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

SESSION_IDLE_TTL_SEC = float(os.getenv("MCP_OUTBOUND_SESSION_IDLE_SEC", "300"))


@dataclass
class _ManagedSession:
    config_key: str
    stack: AsyncExitStack = field(default_factory=AsyncExitStack)
    session: ClientSession | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_used: float = 0.0


_sessions: dict[str, _ManagedSession] = {}
_sessions_lock = asyncio.Lock()


def _config_key(payload: dict[str, Any]) -> str:
    return "|".join(
        [
            payload.get("transport", "stdio"),
            payload.get("command", ""),
            ",".join(payload.get("args") or []),
            str(sorted((payload.get("env") or {}).items())),
        ]
    )


def _stdio_params(payload: dict[str, Any]) -> StdioServerParameters:
    env = {**os.environ, **(payload.get("env") or {})}
    return StdioServerParameters(
        command=payload["command"],
        args=list(payload.get("args") or []),
        env=env,
    )


async def _ensure_session(connection_id: str, payload: dict[str, Any]) -> ClientSession:
    key = _config_key(payload)
    async with _sessions_lock:
        entry = _sessions.get(connection_id)
        if entry is None or entry.config_key != key or entry.session is None:
            if entry is not None:
                await _close_entry(connection_id, entry)
            entry = _ManagedSession(config_key=key)
            _sessions[connection_id] = entry

    async with entry.lock:
        if entry.session is None:
            logger.info(
                "Starting external MCP stdio session connection_id=%s command=%s",
                connection_id,
                payload.get("command"),
            )
            read, write = await entry.stack.enter_async_context(
                stdio_client(_stdio_params(payload))
            )
            session = await entry.stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            entry.session = session
        entry.last_used = asyncio.get_event_loop().time()
        return entry.session


async def _close_entry(connection_id: str, entry: _ManagedSession) -> None:
    try:
        await entry.stack.aclose()
    except Exception as exc:
        logger.warning("Error closing MCP session %s: %s", connection_id, exc)
    finally:
        entry.session = None


async def close_session(connection_id: str) -> None:
    async with _sessions_lock:
        entry = _sessions.pop(connection_id, None)
    if entry:
        await _close_entry(connection_id, entry)


async def list_tools(payload: dict[str, Any]) -> list[dict]:
    connection_id = payload["connection_id"]
    session = await _ensure_session(connection_id, payload)
    result = await session.list_tools()
    tools: list[dict] = []
    for tool in result.tools:
        tools.append(
            {
                "name": tool.name,
                "description": tool.description or "",
                "inputSchema": tool.inputSchema or {"type": "object", "properties": {}},
            }
        )
    return tools


async def call_tool(payload: dict[str, Any]) -> str:
    connection_id = payload["connection_id"]
    tool_name = payload["tool_name"]
    arguments = payload.get("arguments") or {}
    session = await _ensure_session(connection_id, payload)
    result = await session.call_tool(tool_name, arguments)
    parts: list[str] = []
    for block in result.content or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    if parts:
        return "\n".join(parts)
    if getattr(result, "structuredContent", None) is not None:
        import json

        return json.dumps(result.structuredContent, ensure_ascii=False)
    return ""
