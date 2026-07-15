"""Build AgentLoop tools that proxy to external MCP servers."""

from __future__ import annotations

import json
import logging
from typing import Any

from api.ai_layers.mcp_external_access import (
    prefixed_tool_name,
    resolve_remote_tools_for_connection,
)
from api.ai_layers.models import MCPExternalConnection

logger = logging.getLogger(__name__)


def _serialize_tool_result(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if hasattr(result, "model_dump"):
        return json.dumps(result.model_dump(), ensure_ascii=False)
    if isinstance(result, (dict, list)):
        return json.dumps(result, ensure_ascii=False)
    content = getattr(result, "content", None)
    if content is not None:
        parts: list[str] = []
        for block in content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
            elif isinstance(block, dict) and block.get("text"):
                parts.append(str(block["text"]))
        if parts:
            return "\n".join(parts)
    return str(result)


def build_external_mcp_tools(
    connections: list[MCPExternalConnection],
) -> list[dict]:
    """Create AgentTool dicts for attached external MCP connections."""
    from api.ai_layers.mcp_outbound_client import call_external_mcp_tool

    tools: list[dict] = []
    for connection in connections:
        remote_tools = resolve_remote_tools_for_connection(connection)
        for remote in remote_tools:
            remote_name = remote.get("name")
            if not remote_name:
                continue
            tool_name = prefixed_tool_name(connection, remote_name)
            description = remote.get("description") or f"External MCP tool: {remote_name}"
            parameters = remote.get("inputSchema") or {
                "type": "object",
                "properties": {},
            }
            conn_id = str(connection.id)
            cmd = connection.command
            args = list(connection.args or [])
            env = dict(connection.env or {})
            transport = connection.transport

            def _proxy_fn(
                _conn_id=conn_id,
                _remote_name=remote_name,
                _cmd=cmd,
                _args=args,
                _env=env,
                _transport=transport,
                **kwargs: Any,
            ) -> str:
                return call_external_mcp_tool(
                    connection_id=_conn_id,
                    command=_cmd,
                    args=_args,
                    env=_env,
                    transport=_transport,
                    tool_name=_remote_name,
                    arguments=kwargs,
                )

            tools.append(
                {
                    "name": tool_name,
                    "description": f"[{connection.name}] {description}",
                    "parameters": parameters,
                    "function": _proxy_fn,
                }
            )
            logger.info(
                "Registered external MCP tool %s for connection %s",
                tool_name,
                connection.name,
            )
    return tools
