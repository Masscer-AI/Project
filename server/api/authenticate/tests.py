from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient

from api.authenticate.models import Organization, OrganizationInvite, Token


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


class OrganizationInviteFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(
            username="orgowner",
            email="owner@test.com",
            password="owner-password-123",
        )
        self.org = Organization.objects.create(name="Acme Org", owner=self.owner)
        self.login_token, _ = Token.get_or_create(user=self.owner, token_type="login")

    def _auth_headers(self):
        return {"HTTP_AUTHORIZATION": f"Token {self.login_token.key}"}

    @patch.object(OrganizationInvite, "generate_raw_token", return_value="test-invite-token-xyz")
    @patch("api.authenticate.views.EmailService")
    def test_create_invite_sends_email(self, email_service_cls, _token_mock):
        email_service = email_service_cls.return_value

        response = self.client.post(
            f"/v1/auth/organizations/{self.org.id}/invites/",
            data={
                "email": "newmember@test.com",
                "name": "New Member",
                "bio": "Hello",
            },
            format="json",
            **self._auth_headers(),
        )

        self.assertEqual(response.status_code, 201)
        email_service.send_email.assert_called_once()
        self.assertTrue(
            OrganizationInvite.objects.filter(
                organization=self.org,
                email="newmember@test.com",
                status=OrganizationInvite.Status.PENDING,
            ).exists()
        )

    def test_invite_signup_get_returns_org_metadata(self):
        from datetime import timedelta

        from django.utils import timezone as dj_tz

        from api.authenticate.models import hash_organization_invite_token

        raw = "metadata-invite-token"
        OrganizationInvite.objects.create(
            organization=self.org,
            email="meta@test.com",
            name="Meta User",
            bio="",
            invited_by=self.owner,
            token_hash=hash_organization_invite_token(raw),
            status=OrganizationInvite.Status.PENDING,
            invite_expires_at=dj_tz.now() + timedelta(days=7),
        )

        response = self.client.get(f"/v1/auth/signup?invite={raw}")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("invite_valid"))
        self.assertEqual(data.get("email"), "meta@test.com")
        self.assertEqual(data.get("organization", {}).get("name"), "Acme Org")

    @patch.object(OrganizationInvite, "generate_raw_token", return_value="accept-invite-token")
    @patch("api.authenticate.views.EmailService")
    def test_invite_signup_accepts_and_creates_user(self, _email_cls, _token_mock):
        self.client.post(
            f"/v1/auth/organizations/{self.org.id}/invites/",
            data={"email": "joiner@test.com", "name": "Joiner"},
            format="json",
            **self._auth_headers(),
        )

        response = self.client.post(
            "/v1/auth/signup",
            data={
                "invite_token": "accept-invite-token",
                "password": "join-password-123",
                "confirm_password": "join-password-123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="joiner@test.com")
        self.assertTrue(user.check_password("join-password-123"))
        self.assertEqual(user.profile.organization_id, self.org.id)

        inv = OrganizationInvite.objects.get(email="joiner@test.com", organization=self.org)
        self.assertEqual(inv.status, OrganizationInvite.Status.ACCEPTED)
        self.assertEqual(inv.accepted_user_id, user.id)

    def test_invite_signup_rejects_bad_token(self):
        response = self.client.post(
            "/v1/auth/signup",
            data={
                "invite_token": "no-such-token",
                "password": "join-password-123",
                "confirm_password": "join-password-123",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("error"), "invalid-or-expired-invite")

    @patch.object(OrganizationInvite, "generate_raw_token", return_value="revoke-invite-token")
    @patch("api.authenticate.views.EmailService")
    def test_revoke_pending_invite(self, _email_cls, _token_mock):
        create_resp = self.client.post(
            f"/v1/auth/organizations/{self.org.id}/invites/",
            data={"email": "revoke@test.com"},
            format="json",
            **self._auth_headers(),
        )
        self.assertEqual(create_resp.status_code, 201)
        invite_id = create_resp.json()["invite"]["id"]

        del_resp = self.client.delete(
            f"/v1/auth/organizations/{self.org.id}/invites/{invite_id}/",
            **self._auth_headers(),
        )
        self.assertEqual(del_resp.status_code, 200)

        inv = OrganizationInvite.objects.get(id=invite_id)
        self.assertEqual(inv.status, OrganizationInvite.Status.CANCELLED)

        bad = self.client.get("/v1/auth/signup?invite=revoke-invite-token")
        self.assertEqual(bad.status_code, 400)
