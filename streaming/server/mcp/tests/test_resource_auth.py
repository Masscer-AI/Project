"""Tests for MCP resource server auth wrapper and protected-resource metadata."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import PlainTextResponse

from server.mcp.oauth_metadata import router as oauth_metadata_router
from server.mcp.resource_auth import wrap_mcp_app


async def _inner_mcp_app(scope, receive, send):
    response = PlainTextResponse("mcp-ok")
    await response(scope, receive, send)


class _McpNoRedirectSlashMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and scope.get("path") == "/mcp":
            scope = dict(scope)
            scope["path"] = "/mcp/"
            if scope.get("raw_path") == b"/mcp":
                scope["raw_path"] = b"/mcp/"
        await self.app(scope, receive, send)


class MCPResourceAuthTests(unittest.TestCase):
    def setUp(self):
        os.environ["FRONTEND_URL"] = "https://app.masscer-ai.com"
        os.environ["INTERNAL_MCP_INTROSPECT_TOKEN"] = "test-introspect-secret"
        app = FastAPI(redirect_slashes=False)
        app.mount("/mcp", wrap_mcp_app(_inner_mcp_app))
        app.add_middleware(_McpNoRedirectSlashMiddleware)
        self.client = TestClient(app)

    def test_unauthenticated_mcp_returns_401_with_www_authenticate(self):
        res = self.client.post("/mcp/")
        self.assertEqual(res.status_code, 401)
        www = res.headers.get("www-authenticate", "")
        self.assertIn("resource_metadata=", www)
        self.assertIn("oauth-protected-resource", www)
        self.assertIn("invalid_token", www)

    def test_unauthenticated_mcp_no_trailing_slash_is_not_redirect(self):
        """Claude posts to the resource URL without a trailing slash."""
        res = self.client.post("/mcp", follow_redirects=False)
        self.assertNotIn(res.status_code, (301, 302, 307, 308))
        self.assertEqual(res.status_code, 401)

    @patch("server.mcp.resource_auth._introspect_token", return_value=True)
    def test_valid_token_passes_to_inner_app(self, _mock_intro):
        res = self.client.post(
            "/mcp/",
            headers={"Authorization": "Bearer good-token"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.text, "mcp-ok")

    @patch("server.mcp.resource_auth._introspect_token", return_value=False)
    def test_invalid_token_returns_401(self, _mock_intro):
        res = self.client.post(
            "/mcp/",
            headers={"Authorization": "Bearer bad-token"},
        )
        self.assertEqual(res.status_code, 401)


class OAuthProtectedResourceMetadataTests(unittest.TestCase):
    def setUp(self):
        os.environ["FRONTEND_URL"] = "https://app.masscer-ai.com"
        app = FastAPI()
        app.include_router(oauth_metadata_router)
        self.client = TestClient(app)

    def test_protected_resource_metadata_shape(self):
        res = self.client.get("/.well-known/oauth-protected-resource")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["resource"], "https://app.masscer-ai.com/mcp")
        self.assertEqual(data["authorization_servers"], ["https://app.masscer-ai.com"])
        self.assertIn("offline_access", data["scopes_supported"])
        self.assertIn("header", data["bearer_methods_supported"])


if __name__ == "__main__":
    unittest.main()
