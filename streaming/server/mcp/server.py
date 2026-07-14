"""
Masscer MCP protocol server (Streamable HTTP).

Exposes each allowed Masscer agent as an MCP tool. Tool execution proxies to
the Django MCP gateway which runs the production Celery AgentLoop.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from collections.abc import AsyncIterator
from typing import Any

import anyio
import httpx
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.types import Receive, Scope, Send

from server.mcp.auth import extract_bearer_from_scope, get_mcp_bearer_token, set_mcp_bearer_token
from server.mcp.django_client import DjangoMCPClient

logger = logging.getLogger(__name__)

MCP_POLL_INTERVAL_SEC = float(os.getenv("MCP_POLL_INTERVAL_SEC", "2.0"))
MCP_POLL_TIMEOUT_SEC = float(os.getenv("MCP_POLL_TIMEOUT_SEC", "240"))


def _agent_tool_from_payload(agent: dict[str, Any]) -> types.Tool:
    return types.Tool(
        name=agent["tool_name"],
        description=f"{agent['name']}: {agent.get('description', '')}",
        inputSchema=agent.get("input_schema") or {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "conversation_id": {"type": "string"},
            },
            "required": ["message"],
        },
    )


def create_mcp_server() -> Server:
    app = Server("masscer-agents")

    @app.list_tools()
    async def list_tools() -> list[types.Tool]:
        token = get_mcp_bearer_token()
        if not token:
            raise ValueError("Authorization Bearer token required")

        client = DjangoMCPClient(token)
        try:
            agents = await client.list_agents()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                raise ValueError("Invalid or revoked MCP credential") from exc
            raise

        return [_agent_tool_from_payload(a) for a in agents]

    @app.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.ContentBlock]:
        token = get_mcp_bearer_token()
        if not token:
            raise ValueError("Authorization Bearer token required")

        message = (arguments or {}).get("message", "").strip()
        if not message:
            raise ValueError("message is required")

        conversation_id = (arguments or {}).get("conversation_id")
        client = DjangoMCPClient(token)

        agents = await client.list_agents()
        agent = next((a for a in agents if a.get("tool_name") == name), None)
        if not agent:
            raise ValueError(f"Unknown tool: {name}")

        run_resp = await client.run_agent(
            agent_slug=agent["slug"],
            message=message,
            conversation_id=conversation_id,
        )

        if run_resp.get("takeover"):
            return [
                types.TextContent(
                    type="text",
                    text="Message accepted during human takeover; agent was skipped.",
                )
            ]

        task_id = run_resp.get("task_id")
        if not task_id:
            raise ValueError("Agent task was not started")

        ctx = app.request_context
        elapsed = 0.0
        while elapsed < MCP_POLL_TIMEOUT_SEC:
            result = await client.get_task_result(task_id)
            status = result.get("status")

            if status == "pending":
                if ctx and ctx.session:
                    await ctx.session.send_log_message(
                        level="info",
                        data=f"Agent still running ({int(elapsed)}s)…",
                        logger="masscer-mcp",
                        related_request_id=ctx.request_id,
                    )
                await anyio.sleep(MCP_POLL_INTERVAL_SEC)
                elapsed += MCP_POLL_INTERVAL_SEC
                continue

            if status == "failed":
                err = result.get("error", "Agent task failed")
                raise RuntimeError(err)

            output = result.get("output", "")
            conv_id = result.get("conversation_id") or run_resp.get("conversation_id")
            payload = {
                "answer": output,
                "conversation_id": conv_id,
                "message_id": result.get("message_id"),
                "task_id": task_id,
            }
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(payload, ensure_ascii=False, indent=2),
                )
            ]

        raise TimeoutError(
            f"Agent task timed out after {int(MCP_POLL_TIMEOUT_SEC)} seconds"
        )

    return app


_mcp_server = create_mcp_server()
_session_manager = StreamableHTTPSessionManager(
    app=_mcp_server,
    event_store=None,
    json_response=True,
    stateless=True,
)


async def handle_streamable_http(scope: Scope, receive: Receive, send: Send) -> None:
    token = extract_bearer_from_scope(scope)
    set_mcp_bearer_token(token)
    try:
        await _session_manager.handle_request(scope, receive, send)
    finally:
        set_mcp_bearer_token(None)


@contextlib.asynccontextmanager
async def mcp_lifespan() -> AsyncIterator[None]:
    async with _session_manager.run():
        logger.info("Masscer MCP session manager started")
        yield
        logger.info("Masscer MCP session manager stopped")
