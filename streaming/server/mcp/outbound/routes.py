"""Internal HTTP routes for Django/Celery to call external MCP servers."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from server.mcp.outbound.session_manager import call_tool, list_tools

router = APIRouter(prefix="/internal/mcp", tags=["internal-mcp"])


class MCPConnectionPayload(BaseModel):
    connection_id: str
    transport: str = "stdio"
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)


class MCPCallPayload(MCPConnectionPayload):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


def _verify_token(authorization: str | None) -> None:
    expected = os.getenv("INTERNAL_MCP_PROXY_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=503, detail="INTERNAL_MCP_PROXY_TOKEN not configured")
    if not authorization or authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/list-tools")
async def mcp_list_tools(
    payload: MCPConnectionPayload,
    authorization: str | None = Header(default=None),
):
    _verify_token(authorization)
    if payload.transport != "stdio":
        raise HTTPException(status_code=400, detail="Only stdio transport is supported")
    if not payload.command:
        raise HTTPException(status_code=400, detail="command is required")
    try:
        tools = await list_tools(payload.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"tools": tools}


@router.post("/call")
async def mcp_call_tool(
    payload: MCPCallPayload,
    authorization: str | None = Header(default=None),
):
    _verify_token(authorization)
    if payload.transport != "stdio":
        raise HTTPException(status_code=400, detail="Only stdio transport is supported")
    if not payload.command:
        raise HTTPException(status_code=400, detail="command is required")
    if not payload.tool_name:
        raise HTTPException(status_code=400, detail="tool_name is required")
    try:
        output = await call_tool(payload.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"output": output}
