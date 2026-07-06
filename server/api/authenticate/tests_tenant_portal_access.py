from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from api.authenticate.auth_handoff import create_handoff_code
from api.authenticate.models import Organization, OrganizationTenant, Token, UserProfile
from api.authenticate.tenant_portal_access import WRONG_ORGANIZATION_PORTAL_CODE


@override_settings(FRONTEND_URL="http://localhost")
class TenantPortalLoginAccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.acme_owner = User.objects.create_user(
            username="acmeowner",
            email="owner@acme.test",
            password="password-123",
        )
        self.acme_org = Organization.objects.create(
            name="Acme Org",
            owner=self.acme_owner,
        )
        OrganizationTenant.objects.create(
            organization=self.acme_org,
            subdomain="acme",
        )

        self.other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.test",
            password="password-123",
        )
        self.other_org = Organization.objects.create(
            name="Other Org",
            owner=self.other_user,
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.other_user)
        profile.organization = self.other_org
        profile.save()

    def test_login_denied_for_user_from_different_org_on_tenant_portal(self):
        response = self.client.post(
            "/v1/auth/login",
            data={
                "email": self.other_user.email,
                "password": "password-123",
                "portal_origin": "http://acme.localhost",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data.get("code"), WRONG_ORGANIZATION_PORTAL_CODE)
        self.assertEqual(response.data.get("redirect_to"), "http://localhost/login")

    def test_login_allowed_for_tenant_org_owner(self):
        response = self.client.post(
            "/v1/auth/login",
            data={
                "email": self.acme_owner.email,
                "password": "password-123",
                "portal_origin": "http://acme.localhost",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)

    def test_login_without_portal_origin_ignores_tenant_constraint(self):
        response = self.client.post(
            "/v1/auth/login",
            data={
                "email": self.other_user.email,
                "password": "password-123",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)

    def test_open_signup_denied_on_tenant_portal(self):
        response = self.client.post(
            "/v1/auth/signup",
            data={
                "email": "brandnew@example.test",
                "password": "password-123",
                "organization_name": "New Workspace",
                "portal_origin": "http://acme.localhost",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data.get("code"), "tenant_portal_signup_forbidden")


@override_settings(FRONTEND_URL="http://localhost")
class TenantPortalGoogleHandoffTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.acme_owner = User.objects.create_user(
            username="acmeowner",
            email="owner@acme.test",
            password="password-123",
        )
        self.acme_org = Organization.objects.create(
            name="Acme Org",
            owner=self.acme_owner,
        )
        OrganizationTenant.objects.create(
            organization=self.acme_org,
            subdomain="acme",
        )
        Token.get_or_create(user=self.acme_owner, token_type="login")

        self.other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.test",
            password="password-123",
        )
        self.other_org = Organization.objects.create(
            name="Other Org",
            owner=self.other_user,
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.other_user)
        profile.organization = self.other_org
        profile.save()
        Token.get_or_create(user=self.other_user, token_type="login")

    def tearDown(self):
        cache.clear()

    def _mock_google_userinfo(self, email: str):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "email": email,
            "name": "Test User",
            "picture": "",
        }
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    @patch("api.authenticate.views.http_requests.get")
    def test_google_login_with_return_to_allows_matching_org_member(self, mock_get):
        mock_get.return_value = self._mock_google_userinfo(self.acme_owner.email)
        response = self.client.post(
            "/v1/auth/google",
            data={
                "access_token": "fake-token",
                "return_to": "http://acme.localhost",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("handoff_code", response.data)

    @patch("api.authenticate.views.http_requests.get")
    def test_google_login_with_return_to_denies_other_org_member(self, mock_get):
        mock_get.return_value = self._mock_google_userinfo(self.other_user.email)
        response = self.client.post(
            "/v1/auth/google",
            data={
                "access_token": "fake-token",
                "return_to": "http://acme.localhost",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data.get("code"), WRONG_ORGANIZATION_PORTAL_CODE)

    def test_handoff_exchange_denies_other_org_member(self):
        code = create_handoff_code(self.other_user.id, "http://acme.localhost")
        response = self.client.post(
            "/v1/auth/handoff/exchange",
            data={"code": code},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data.get("code"), WRONG_ORGANIZATION_PORTAL_CODE)

    def test_handoff_exchange_allows_matching_org_member(self):
        code = create_handoff_code(self.acme_owner.id, "http://acme.localhost")
        response = self.client.post(
            "/v1/auth/handoff/exchange",
            data={"code": code},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)
