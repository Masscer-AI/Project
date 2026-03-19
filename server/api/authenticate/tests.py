from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient

from api.authenticate.models import Token


class PasswordResetFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="old-password-123",
        )

    @patch("api.authenticate.views.EmailService")
    def test_password_reset_request_returns_200_for_existing_email(self, email_service_cls):
        email_service = email_service_cls.return_value

        response = self.client.post(
            "/v1/auth/password-reset/request",
            data={"email": self.user.email},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        email_service.send_email.assert_called_once()

    @patch("api.authenticate.views.EmailService")
    def test_password_reset_request_returns_200_for_missing_email(self, email_service_cls):
        response = self.client.post(
            "/v1/auth/password-reset/request",
            data={"email": "missing@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        email_service_cls.assert_not_called()

    def test_password_reset_confirm_rejects_invalid_token(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))

        response = self.client.post(
            "/v1/auth/password-reset/confirm",
            data={
                "uid": uid,
                "token": "invalid-token",
                "new_password": "new-password-123",
                "confirm_password": "new-password-123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("error"), "invalid-or-expired-reset-link")

    def test_password_reset_confirm_updates_password_and_revokes_login_tokens(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        login_token, _ = Token.get_or_create(user=self.user, token_type="login")
        self.assertTrue(Token.objects.filter(pk=login_token.pk).exists())

        response = self.client.post(
            "/v1/auth/password-reset/confirm",
            data={
                "uid": uid,
                "token": token,
                "new_password": "new-password-123",
                "confirm_password": "new-password-123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("new-password-123"))
        self.assertFalse(Token.objects.filter(user=self.user, token_type="login").exists())
