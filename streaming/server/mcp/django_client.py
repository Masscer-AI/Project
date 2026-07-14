"""Django API client for MCP gateway endpoints."""

from __future__ import annotations

import os
from typing import Any

import httpx

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")


class DjangoMCPClient:
    """HTTP client for authenticated MCP gateway endpoints on Django."""

    def __init__(self, bearer_token: str, api_url: str | None = None):
        self.bearer_token = bearer_token
        self.api_url = (api_url or API_URL).rstrip("/")
        self._headers = {"Authorization": f"Bearer {bearer_token}"}

    async def list_agents(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.api_url}/v1/ai_layers/mcp/agents/",
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("agents", [])

    async def run_agent(
        self,
        *,
        agent_slug: str,
        message: str,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "agent_slug": agent_slug,
            "message": message,
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.api_url}/v1/ai_layers/mcp/run/",
                headers={**self._headers, "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_task_result(self, task_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.api_url}/v1/ai_layers/mcp/result/{task_id}/",
                headers=self._headers,
            )
            if resp.status_code == 500:
                return resp.json()
            resp.raise_for_status()
            return resp.json()
