"""
Tests for the integrations app.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from api.authenticate.models import Organization, UserProfile
from api.integrations.models import Integration, IntegrationProvider
from api.integrations.schemas import validate_provider_metadata
from api.integrations.services import parse_owner_type


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

    @patch("api.integrations.views.FeatureFlagService.is_feature_enabled", return_value=(True, "is-owner"))
    @patch("api.integrations.views.get_google_client_secret", return_value="secret")
    @patch("api.integrations.views.get_google_client_id", return_value="client-id")
    @patch("api.integrations.views.get_provider")
    def test_callback_creates_integration(self, mock_get_provider, *_ff):
        state = "test-state-token"
        cache.set(
            "integrations_oauth_state:test-state-token",
            {
                "user_id": self.user.id,
                "provider": "google_drive",
                "owner_type": "user",
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
        self.assertTrue(
            Integration.objects.filter(
                user=self.user,
                provider=IntegrationProvider.GOOGLE_DRIVE,
            ).exists()
        )
