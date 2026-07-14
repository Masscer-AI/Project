"""
Tests for the integrations app.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from api.authenticate.models import Organization, UserProfile
from api.integrations.models import Integration, IntegrationProvider
from api.integrations.schemas import validate_provider_metadata
from api.integrations.services import (
    build_integrations_return_url,
    get_redirect_uri,
    parse_owner_type,
    validate_return_to,
)


class GoogleDriveMetadataTests(SimpleTestCase):
    def test_valid_metadata(self):
        meta = validate_provider_metadata(
            "google_drive",
            {"account_email": "a@b.com", "granted_scopes": ["drive.readonly"]},
        )
        self.assertEqual(meta["account_email"], "a@b.com")

    def test_rejects_unknown_fields(self):
        with self.assertRaises(Exception):
            validate_provider_metadata("google_drive", {"unknown": True})

    def test_unknown_provider_passes_through(self):
        self.assertEqual(validate_provider_metadata("other", {"x": 1}), {"x": 1})


class ParseOwnerTypeTests(SimpleTestCase):
    def test_defaults_to_user(self):
        self.assertEqual(parse_owner_type(None), "user")

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            parse_owner_type("invalid")


@override_settings(FRONTEND_URL="http://localhost")
class IntegrationOAuthServicesTests(SimpleTestCase):
    def test_get_redirect_uri_uses_frontend_url(self):
        request = RequestFactory().get("/v1/integrations/google_drive/connect/")
        request.META["HTTP_HOST"] = "acme.localhost"
        self.assertEqual(
            get_redirect_uri(request, "google_drive"),
            "http://localhost/v1/integrations/google_drive/callback/",
        )

    def test_validate_return_to_accepts_tenant_subdomain(self):
        self.assertEqual(
            validate_return_to("http://acme.localhost/integrations"),
            "http://acme.localhost/integrations",
        )

    def test_validate_return_to_rejects_external_host(self):
        self.assertIsNone(
            validate_return_to("https://evil.com/integrations")
        )

    def test_build_integrations_return_url_appends_error(self):
        url = build_integrations_return_url(
            "http://acme.localhost/integrations",
            error="token_exchange_failed",
        )
        self.assertEqual(
            url,
            "http://acme.localhost/integrations?error=token_exchange_failed",
        )


class IntegrationModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u1", email="u1@test.com", password="x")
        self.org = Organization.objects.create(name="Org", owner=self.user)

    def test_user_owner_clean_valid(self):
        integration = Integration(
            user=self.user,
            provider=IntegrationProvider.GOOGLE_DRIVE,
            access_token="tok",
            metadata={"account_email": "u1@test.com"},
        )
        integration.full_clean()

    def test_both_owners_invalid(self):
        integration = Integration(
            user=self.user,
            organization=self.org,
            provider=IntegrationProvider.GOOGLE_DRIVE,
            access_token="tok",
        )
        with self.assertRaises(ValidationError):
            integration.full_clean()

    def test_neither_owner_invalid(self):
        integration = Integration(
            provider=IntegrationProvider.GOOGLE_DRIVE,
            access_token="tok",
        )
        with self.assertRaises(ValidationError):
            integration.full_clean()

    def test_owner_type_user(self):
        integration = Integration.objects.create(
            user=self.user,
            provider=IntegrationProvider.GOOGLE_DRIVE,
            access_token="tok",
            metadata={},
        )
        self.assertEqual(integration.owner_type, "user")

    def test_owner_type_organization(self):
        integration = Integration.objects.create(
            organization=self.org,
            provider=IntegrationProvider.GOOGLE_DRIVE,
            access_token="tok",
            metadata={},
        )
        self.assertEqual(integration.owner_type, "organization")


@override_settings(FRONTEND_URL="http://localhost")
class IntegrationsViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="owner", email="owner@test.com", password="pass")
        self.org = Organization.objects.create(name="Test Org", owner=self.user)
        UserProfile.objects.create(user=self.user, organization=self.org, name="Owner")
        from api.authenticate.models import Token

        self.token, _ = Token.get_or_create(user=self.user, token_type="permanent")

    def _auth_headers(self):
        return {"HTTP_AUTHORIZATION": f"Token {self.token.key}"}

    @patch("api.integrations.views.user_can_manage_integrations", return_value=True)
    @patch("api.integrations.views.get_google_client_id", return_value="client-id")
    @patch("api.integrations.views.get_google_client_secret", return_value="secret")
    def test_connect_returns_authorization_url(self, *_mocks):
        url = reverse("integrations:connect", kwargs={"provider": "google_drive"})
        resp = self.client.get(
            f"{url}?owner=user",
            **self._auth_headers(),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("authorization_url", data)
        self.assertEqual(data["owner_type"], "user")
        self.assertIn("accounts.google.com", data["authorization_url"])

    def test_list_requires_auth(self):
        url = reverse("integrations:list")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 401)

    @patch("api.integrations.views.user_can_manage_integrations", return_value=True)
    def test_list_returns_integrations(self, _mock):
        Integration.objects.create(
            user=self.user,
            provider=IntegrationProvider.GOOGLE_DRIVE,
            access_token="tok",
            account_email="drive@test.com",
            metadata={},
        )
        url = reverse("integrations:list")
        resp = self.client.get(url, **self._auth_headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["integrations"]), 1)
        self.assertEqual(data["integrations"][0]["owner_type"], "user")

    @patch("api.integrations.views.user_can_manage_integrations", return_value=True)
    @patch("api.integrations.views.get_google_client_id", return_value="client-id")
    @patch("api.integrations.views.get_google_client_secret", return_value="secret")
    @patch("api.integrations.views.get_provider")
    def test_connect_stores_return_to(self, mock_get_provider, *_mocks):
        provider_instance = MagicMock()
        provider_instance.get_authorization_url.return_value = (
            "https://accounts.google.com/o/oauth2/v2/auth?state=abc"
        )
        mock_get_provider.return_value = provider_instance

        url = reverse("integrations:connect", kwargs={"provider": "google_drive"})
        return_to = "http://acme.localhost/integrations"
        resp = self.client.get(
            f"{url}?owner=user&return_to={return_to}",
            **self._auth_headers(),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(
            data["redirect_uri"],
            "http://localhost/v1/integrations/google_drive/callback/",
        )
        state = data["state"]
        cached = cache.get(f"integrations_oauth_state:{state}")
        self.assertEqual(cached["return_to"], return_to)

    @override_settings(FRONTEND_URL="http://localhost")
    @patch("api.integrations.views.FeatureFlagService.is_feature_enabled", return_value=(True, "is-owner"))
    @patch("api.integrations.views.get_google_client_secret", return_value="secret")
    @patch("api.integrations.views.get_google_client_id", return_value="client-id")
    @patch("api.integrations.views.get_provider")
    def test_callback_creates_integration(self, mock_get_provider, *_ff):
        state = "test-state-token"
        return_to = "http://acme.localhost/integrations"
        cache.set(
            "integrations_oauth_state:test-state-token",
            {
                "user_id": self.user.id,
                "provider": "google_drive",
                "owner_type": "user",
                "return_to": return_to,
            },
            timeout=600,
        )

        provider_instance = MagicMock()
        provider_instance.exchange_code_for_token.return_value = {
            "access_token": "at",
            "refresh_token": "rt",
            "expires_in": 3600,
            "scope": "https://www.googleapis.com/auth/drive.readonly",
        }
        provider_instance.fetch_account_info.return_value = {
            "email": "drive@test.com",
            "name": "Drive User",
        }
        provider_instance.build_metadata_from_token_response.return_value = {
            "account_email": "drive@test.com",
            "granted_scopes": ["https://www.googleapis.com/auth/drive.readonly"],
        }
        mock_get_provider.return_value = provider_instance

        url = reverse("integrations:callback", kwargs={"provider": "google_drive"})
        resp = self.client.get(f"{url}?code=abc&state={state}")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], return_to)
        self.assertTrue(
            Integration.objects.filter(
                user=self.user,
                provider=IntegrationProvider.GOOGLE_DRIVE,
            ).exists()
        )


class DriveXlsxImportTests(SimpleTestCase):
    def test_extract_text_from_drive_xlsx_bytes(self):
        from api.integrations.drive_import import _extract_text_from_drive_bytes
        from api.utils.spreadsheet_tools import build_xlsx_bytes_from_sheets

        raw = build_xlsx_bytes_from_sheets(
            [
                {
                    "name": "Inventory",
                    "headers": ["SKU", "Qty"],
                    "rows": [["A-1", 5]],
                }
            ]
        )
        text, file_name = _extract_text_from_drive_bytes(
            raw,
            "inventory.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertEqual(file_name, "inventory.xlsx")
        self.assertIn("SKU | Qty", text)
        self.assertIn("A-1 | 5", text)
