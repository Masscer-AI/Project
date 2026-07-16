"""Tests for MCP OAuth authorization server."""

from __future__ import annotations

import base64
import hashlib
import secrets
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from authlib.oauth2.rfc7636 import create_s256_code_challenge
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from api.ai_layers.models import Agent, LanguageModel, MCPClient
from api.authenticate.models import Token
from api.mcp_oauth.crypto import generate_token, hash_secret
from api.mcp_oauth.models import OAuthAuthorizationCode, OAuthClient
from api.mcp_oauth.token_service import (
    exchange_authorization_code,
    introspect_token,
    mint_authorization_code,
    refresh_access_token,
)
from api.providers.models import AIProvider


@override_settings(
    FRONTEND_URL="https://app.masscer-ai.com",
    INTERNAL_MCP_INTROSPECT_TOKEN="test-introspect-secret",
    MCP_OAUTH_ACCESS_TOKEN_TTL=3600,
    MCP_OAUTH_REFRESH_TOKEN_TTL=86400,
    MCP_OAUTH_AUTH_CODE_TTL=60,
)
class MCPOAuthServerTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="oauth_user", email="oauth@test.com", password="x"
        )
        self.login_token = Token.objects.create(user=self.user, token_type="permanent")
        provider = AIProvider.objects.create(name="OpenAI-oauth")
        llm = LanguageModel.objects.create(
            provider=provider, slug="gpt-oauth", name="GPT OAuth"
        )
        self.agent = Agent.objects.create(
            name="OAuth Agent",
            salute="hi",
            act_as="help",
            user=self.user,
            slug="oauth-agent",
            llm=llm,
            model_slug=llm.slug,
        )
        self.oauth_client, self.client_secret = OAuthClient.create_manual(
            client_name="Test Connector",
            redirect_uris=["https://claude.ai/api/mcp/auth_callback"],
            owner_user=self.user,
            confidential=True,
        )
        self.code_verifier = secrets.token_urlsafe(48)
        self.code_challenge = create_s256_code_challenge(self.code_verifier)
        self.resource = "https://app.masscer-ai.com/mcp"

    def test_authorization_server_metadata(self):
        res = self.client.get("/.well-known/oauth-authorization-server")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["issuer"], "https://app.masscer-ai.com")
        self.assertIn("S256", data["code_challenge_methods_supported"])
        self.assertTrue(data["client_id_metadata_document_supported"])

    def test_oauth_authorize_redirects_to_consent(self):
        res = self.client.get(
            "/oauth/authorize",
            {
                "client_id": self.oauth_client.client_id,
                "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
                "response_type": "code",
                "state": "abc",
                "scope": "mcp offline_access",
                "resource": self.resource,
                "code_challenge": self.code_challenge,
                "code_challenge_method": "S256",
            },
        )
        self.assertEqual(res.status_code, 302)
        self.assertIn("/oauth/consent?req=", res["Location"])

    def test_oauth_authorize_rejects_bad_redirect(self):
        res = self.client.get(
            "/oauth/authorize",
            {
                "client_id": self.oauth_client.client_id,
                "redirect_uri": "https://evil.example/callback",
                "response_type": "code",
                "resource": self.resource,
                "code_challenge": self.code_challenge,
                "code_challenge_method": "S256",
            },
        )
        self.assertEqual(res.status_code, 400)

    def test_token_exchange_with_pkce(self):
        mcp_client = MCPClient.objects.create(name="OAuth Grant", user=self.user)
        raw_code = mint_authorization_code(
            client=self.oauth_client,
            user=self.user,
            mcp_client=mcp_client,
            redirect_uri="https://claude.ai/api/mcp/auth_callback",
            code_challenge=self.code_challenge,
            scope="mcp offline_access",
            resource=self.resource,
        )
        creds = base64.b64encode(
            f"{self.oauth_client.client_id}:{self.client_secret}".encode()
        ).decode()
        res = self.client.post(
            "/oauth/token",
            {
                "grant_type": "authorization_code",
                "code": raw_code,
                "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
                "code_verifier": self.code_verifier,
                "resource": self.resource,
            },
            HTTP_AUTHORIZATION=f"Basic {creds}",
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(res.status_code, 200, res.content)
        data = res.json()
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)

    def test_refresh_token_rotation(self):
        mcp_client = MCPClient.objects.create(name="OAuth Grant", user=self.user)
        raw_code = mint_authorization_code(
            client=self.oauth_client,
            user=self.user,
            mcp_client=mcp_client,
            redirect_uri="https://claude.ai/api/mcp/auth_callback",
            code_challenge=self.code_challenge,
            scope="mcp",
            resource=self.resource,
        )
        result = exchange_authorization_code(
            client=self.oauth_client,
            code=raw_code,
            redirect_uri="https://claude.ai/api/mcp/auth_callback",
            code_verifier=self.code_verifier,
            resource=self.resource,
        )
        self.assertIsNotNone(result[0])
        _access, refresh1, _ = result

        rotated = refresh_access_token(
            client=self.oauth_client,
            refresh_token=refresh1,
            resource=self.resource,
        )
        self.assertIsNotNone(rotated[0])
        _access2, refresh2, _ = rotated

        reuse = refresh_access_token(
            client=self.oauth_client,
            refresh_token=refresh1,
            resource=self.resource,
        )
        self.assertIsNone(reuse[0])
        self.assertEqual(reuse[1], "invalid_grant")

    def test_introspect_oauth_and_legacy_tokens(self):
        mcp_client = MCPClient.objects.create(name="Legacy", user=self.user)
        raw_access = generate_token(32)
        from api.mcp_oauth.models import OAuthAccessToken
        from django.utils import timezone
        from datetime import timedelta

        OAuthAccessToken.objects.create(
            token_hash=hash_secret(raw_access),
            client=self.oauth_client,
            user=self.user,
            mcp_client=mcp_client,
            scope="mcp",
            resource=self.resource,
            expires_at=timezone.now() + timedelta(hours=1),
        )
        oauth_intro = introspect_token(raw_access)
        self.assertTrue(oauth_intro["active"])
        self.assertEqual(oauth_intro["mcp_client_id"], str(mcp_client.id))

        legacy = MCPClient.objects.create(name="Key client", user=self.user)
        legacy_intro = introspect_token(legacy.key)
        self.assertTrue(legacy_intro["active"])
        self.assertEqual(legacy_intro["token_type"], "legacy")

    def test_introspect_endpoint_requires_secret(self):
        res = self.client.post(
            "/v1/mcp_oauth/introspect/",
            data='{"token":"x"}',
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 401)

        mcp_client = MCPClient.objects.create(name="X", user=self.user)
        res = self.client.post(
            "/v1/mcp_oauth/introspect/",
            data=f'{{"token":"{mcp_client.key}"}}',
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-introspect-secret",
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["active"])

    @patch("api.mcp_oauth.views.user_can_manage_integrations", return_value=True)
    def test_create_oauth_client_api(self, _can_manage):
        res = self.client.post(
            "/v1/mcp_oauth/clients/",
            data={
                "client_name": "ChatGPT",
                "redirect_uris": ["https://chatgpt.com/connector/oauth/abc"],
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.login_token.key}",
        )
        self.assertEqual(res.status_code, 201, res.content)
        data = res.json()
        self.assertIn("client_id", data)
        self.assertIn("client_secret", data)

    def test_dcr_register(self):
        res = self.client.post(
            "/oauth/register",
            data={
                "client_name": "DCR Client",
                "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
                "token_endpoint_auth_method": "none",
            },
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertIn("client_id", res.json())

    @patch("api.mcp_oauth.cimd.fetch_cimd_document")
    def test_cimd_client_resolution(self, mock_fetch):
        cimd_url = "https://claude.ai/.well-known/oauth-client"
        mock_fetch.return_value = {
            "client_id": cimd_url,
            "client_name": "Claude",
            "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
            "token_endpoint_auth_method": "none",
        }
        from api.mcp_oauth.cimd import resolve_cimd_client

        client = resolve_cimd_client(cimd_url)
        self.assertIsNotNone(client)
        self.assertEqual(client.client_id, cimd_url)

    @patch("api.mcp_oauth.views.user_can_manage_integrations", return_value=True)
    def test_approve_authorize_request(self, _can_manage):
        from api.mcp_oauth.models import OAuthAuthorizationRequest
        from django.utils import timezone
        from datetime import timedelta

        auth_req = OAuthAuthorizationRequest.objects.create(
            client=self.oauth_client,
            redirect_uri="https://claude.ai/api/mcp/auth_callback",
            state="st",
            code_challenge=self.code_challenge,
            scope="mcp",
            resource=self.resource,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        res = self.client.post(
            f"/v1/mcp_oauth/authorize-request/{auth_req.id}/approve/",
            data={
                "credential_name": "Claude connection",
                "allowed_agent_slugs": [self.agent.slug],
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.login_token.key}",
        )
        self.assertEqual(res.status_code, 200, res.content)
        redirect_url = res.json()["redirect_url"]
        parsed = urlparse(redirect_url)
        self.assertEqual(parsed.scheme + "://" + parsed.netloc + parsed.path,
                         "https://claude.ai/api/mcp/auth_callback")
        qs = parse_qs(parsed.query)
        self.assertIn("code", qs)
