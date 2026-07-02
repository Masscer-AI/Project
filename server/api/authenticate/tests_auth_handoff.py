from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from api.authenticate.auth_handoff import create_handoff_code, exchange_handoff_code
from api.authenticate.models import Organization, Token
from api.authenticate.subdomain_utils import validate_auth_return_to_origin, validate_google_auth_redirect_uri


@override_settings(FRONTEND_URL="http://localhost")
class AuthReturnToOriginTests(SimpleTestCase):
    def test_validate_auth_return_to_origin_accepts_tenant_subdomain(self):
        self.assertEqual(
            validate_auth_return_to_origin("http://acme.localhost"),
            "http://acme.localhost",
        )

    def test_validate_auth_return_to_origin_accepts_canonical_frontend(self):
        self.assertEqual(
            validate_auth_return_to_origin("http://localhost"),
            "http://localhost",
        )

    def test_validate_auth_return_to_origin_rejects_path(self):
        self.assertIsNone(validate_auth_return_to_origin("http://acme.localhost/login"))

    def test_validate_auth_return_to_origin_rejects_external_host(self):
        self.assertIsNone(validate_auth_return_to_origin("https://evil.com"))


@override_settings(FRONTEND_URL="http://localhost")
class GoogleAuthRedirectUriTests(SimpleTestCase):
    def test_validate_google_auth_redirect_uri_accepts_canonical_bridge(self):
        self.assertEqual(
            validate_google_auth_redirect_uri("http://localhost/auth/google"),
            "http://localhost/auth/google",
        )

    def test_validate_google_auth_redirect_uri_rejects_tenant_host(self):
        self.assertIsNone(validate_google_auth_redirect_uri("http://acme.localhost/auth/google"))

    def test_validate_google_auth_redirect_uri_rejects_wrong_path(self):
        self.assertIsNone(validate_google_auth_redirect_uri("http://localhost/login"))


@override_settings(FRONTEND_URL="http://localhost")
class AuthHandoffTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="member",
            email="member@example.com",
            password="password-123",
        )

    def tearDown(self):
        cache.clear()

    def test_create_and_exchange_handoff_code(self):
        code = create_handoff_code(self.user.id, "http://acme.localhost")
        result = exchange_handoff_code(code)
        self.assertIsNotNone(result)
        user, return_to = result
        self.assertEqual(user.id, self.user.id)
        self.assertEqual(return_to, "http://acme.localhost")

    def test_exchange_handoff_code_is_single_use(self):
        code = create_handoff_code(self.user.id, "http://acme.localhost")
        self.assertIsNotNone(exchange_handoff_code(code))
        self.assertIsNone(exchange_handoff_code(code))

    def test_handoff_exchange_endpoint_returns_token(self):
        code = create_handoff_code(self.user.id, "http://acme.localhost")
        response = self.client.post(
            "/v1/auth/handoff/exchange",
            data={"code": code},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)
        login_token, _ = Token.get_or_create(user=self.user, token_type="login")
        self.assertEqual(response.data["token"], login_token.key)

    def test_handoff_exchange_rejects_invalid_code(self):
        response = self.client.post(
            "/v1/auth/handoff/exchange",
            data={"code": "not-a-real-code"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)


@override_settings(FRONTEND_URL="http://localhost")
class TenantGoogleLoginHandoffTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.existing_user = User.objects.create_user(
            username="existing",
            email="existing@example.com",
            password="password-123",
        )
        Token.get_or_create(user=self.existing_user, token_type="login")

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
    def test_google_login_with_return_to_blocks_new_signup(self, mock_get):
        mock_get.return_value = self._mock_google_userinfo("newuser@example.com")
        response = self.client.post(
            "/v1/auth/google",
            data={
                "access_token": "fake-token",
                "return_to": "http://acme.localhost",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("No account found", response.data["error"])
        self.assertFalse(User.objects.filter(email="newuser@example.com").exists())

    @patch("api.authenticate.views.http_requests.get")
    def test_google_login_with_return_to_returns_handoff_for_existing_user(self, mock_get):
        mock_get.return_value = self._mock_google_userinfo(self.existing_user.email)
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
        self.assertEqual(response.data["return_to"], "http://acme.localhost")
        self.assertNotIn("token", response.data)

    @patch("api.authenticate.views.http_requests.get")
    def test_google_login_without_return_to_still_creates_user(self, mock_get):
        mock_get.return_value = self._mock_google_userinfo("brandnew@example.com")
        response = self.client.post(
            "/v1/auth/google",
            data={"access_token": "fake-token"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)
        self.assertTrue(User.objects.filter(email="brandnew@example.com").exists())
        self.assertTrue(Organization.objects.filter(owner__email="brandnew@example.com").exists())
