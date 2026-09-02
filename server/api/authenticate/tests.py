from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.test import SimpleTestCase, TestCase
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient

from api.authenticate.models import (
    Organization,
    OrganizationInvite,
    Role,
    RoleAssignment,
    Token,
)


class InviteIntakeSchemaTests(SimpleTestCase):
    def test_normalize_invite_intake_is_lenient_and_keeps_extra_fields(self):
        from api.authenticate.invite_intake import normalize_invite_intake

        self.assertEqual(normalize_invite_intake(None), {})
        self.assertEqual(
            normalize_invite_intake(
                {
                    "person_type": "persona_fisica",
                    "counterparty_role": "",
                    "relationship_status": None,
                    "rfc": " 12n123123123n ",
                    "giro": "alimentos",
                }
            ),
            {
                "person_type": "persona_fisica",
                "rfc": "12N123123123N",
                "giro": "alimentos",
            },
        )
        self.assertEqual(
            normalize_invite_intake({"person_type": "otro"}),
            {"person_type": "otro"},
        )
        with self.assertRaises(ValueError):
            normalize_invite_intake(["not", "an", "object"])



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
        from api.ai_layers.models import LanguageModel
        from api.consumption.models import Currency
        from api.providers.models import AIProvider

        Currency.objects.get_or_create(
            name="Compute Unit", defaults={"one_usd_is": 1000}
        )
        provider = AIProvider.objects.create(name="OpenAI-invite")
        LanguageModel.objects.create(
            provider=provider, slug="gpt-invite", name="GPT Invite"
        )

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

    @patch.object(OrganizationInvite, "generate_raw_token", return_value="role-invite-token")
    @patch("api.authenticate.views.EmailService")
    def test_create_invite_stores_role_and_assigns_on_accept(self, _email_cls, _token_mock):
        role = Role.objects.create(
            organization=self.org, name="Counterparty", enabled=True
        )
        create_resp = self.client.post(
            f"/v1/auth/organizations/{self.org.id}/invites/",
            data={"email": "withrole@test.com", "role_id": str(role.id)},
            format="json",
            **self._auth_headers(),
        )
        self.assertEqual(create_resp.status_code, 201)
        self.assertEqual(create_resp.json()["invite"]["role_id"], str(role.id))
        self.assertEqual(create_resp.json()["invite"]["role_name"], "Counterparty")

        accept = self.client.post(
            "/v1/auth/signup",
            data={
                "invite_token": "role-invite-token",
                "password": "join-password-123",
                "confirm_password": "join-password-123",
            },
            format="json",
        )
        self.assertEqual(accept.status_code, 201)
        user = User.objects.get(email="withrole@test.com")
        assignment = RoleAssignment.objects.get(user=user, organization=self.org)
        self.assertEqual(assignment.role_id, role.id)

    @patch.object(OrganizationInvite, "generate_raw_token", return_value="bad-role-invite")
    @patch("api.authenticate.views.EmailService")
    def test_create_invite_rejects_role_from_other_org(self, _email_cls, _token_mock):
        other = Organization.objects.create(name="Other Org", owner=self.owner)
        role = Role.objects.create(organization=other, name="Foreign", enabled=True)
        response = self.client.post(
            f"/v1/auth/organizations/{self.org.id}/invites/",
            data={"email": "foreignrole@test.com", "role_id": str(role.id)},
            format="json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 404)

    @patch.object(OrganizationInvite, "generate_raw_token", return_value="intake-ignored-token")
    @patch("api.authenticate.views.EmailService")
    def test_create_invite_ignores_intake_payload(self, _email_cls, _token_mock):
        create_resp = self.client.post(
            f"/v1/auth/organizations/{self.org.id}/invites/",
            data={
                "email": "kyb@test.com",
                "name": "ACME SA",
                "intake": {
                    "person_type": "persona_moral",
                    "counterparty_role": "proveedor",
                    "rfc": "XAXX010101000",
                },
            },
            format="json",
            **self._auth_headers(),
        )
        self.assertEqual(create_resp.status_code, 201)
        self.assertEqual(create_resp.json()["invite"]["intake"], {})

        accept = self.client.post(
            "/v1/auth/signup",
            data={
                "invite_token": "intake-ignored-token",
                "password": "join-password-123",
                "confirm_password": "join-password-123",
            },
            format="json",
        )
        self.assertEqual(accept.status_code, 201)
        joiner = User.objects.get(email="kyb@test.com")
        self.assertEqual(joiner.profile.intake, {})
        self.assertEqual(joiner.profile.name, "ACME SA")

    @patch.object(OrganizationInvite, "generate_raw_token", return_value="bad-intake-ignored")
    @patch("api.authenticate.views.EmailService")
    def test_create_invite_ignores_non_object_intake(self, _email_cls, _token_mock):
        response = self.client.post(
            f"/v1/auth/organizations/{self.org.id}/invites/",
            data={
                "email": "badintake@test.com",
                "intake": ["not-an-object"],
            },
            format="json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["invite"]["intake"], {})

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

    def test_organization_list_includes_pld_access_enabled(self):
        self.org.pld_access_enabled = True
        self.org.save(update_fields=["pld_access_enabled"])
        listed = self.client.get(
            "/v1/auth/organizations/",
            **self._auth_headers(),
        )
        self.assertEqual(listed.status_code, 200)
        row = next(r for r in listed.json() if r["id"] == str(self.org.id))
        self.assertTrue(row.get("pld_access_enabled"))
        self.assertFalse(row.get("has_active_role"))

    def test_organization_list_has_active_role_for_assigned_member(self):
        from django.utils import timezone

        from api.authenticate.models import Role, RoleAssignment, Token, UserProfile

        member = User.objects.create_user(
            username="role-member", email="role-member@test.com", password="x"
        )
        UserProfile.objects.update_or_create(
            user=member,
            defaults={"organization": self.org, "is_active": True},
        )
        role = Role.objects.create(
            organization=self.org, name="Staff", enabled=True, capabilities=[]
        )
        RoleAssignment.objects.create(
            user=member,
            organization=self.org,
            role=role,
            from_date=timezone.now().date(),
        )
        token, _ = Token.get_or_create(user=member, token_type="login")
        listed = self.client.get(
            "/v1/auth/organizations/",
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )
        self.assertEqual(listed.status_code, 200)
        row = next(r for r in listed.json() if r["id"] == str(self.org.id))
        self.assertTrue(row.get("has_active_role"))


class CanUseChatBackfillTests(TestCase):
    def setUp(self):
        from django.utils import timezone

        from api.ai_layers.models import LanguageModel
        from api.authenticate.models import UserProfile
        from api.consumption.models import Currency
        from api.providers.models import AIProvider

        Currency.objects.get_or_create(
            name="Compute Unit", defaults={"one_usd_is": 1000}
        )
        provider = AIProvider.objects.create(name="OpenAI-chat-flag")
        LanguageModel.objects.create(
            provider=provider, slug="gpt-chat-flag", name="GPT Chat Flag"
        )

        self.owner = User.objects.create_user(
            username="chat-owner", email="chat-owner@test.com", password="x"
        )
        self.member = User.objects.create_user(
            username="chat-member", email="chat-member@test.com", password="x"
        )
        self.invitee = User.objects.create_user(
            username="chat-invitee", email="chat-invitee@test.com", password="x"
        )
        self.org = Organization.objects.create(name="Chat Org", owner=self.owner)
        UserProfile.objects.update_or_create(
            user=self.owner,
            defaults={"organization": self.org, "is_active": True},
        )
        UserProfile.objects.update_or_create(
            user=self.member,
            defaults={"organization": self.org, "is_active": True},
        )
        UserProfile.objects.update_or_create(
            user=self.invitee,
            defaults={"organization": None, "is_active": True},
        )
        self.role = Role.objects.create(
            organization=self.org,
            name="Member",
            enabled=True,
            capabilities=["train-agents"],
        )
        self.other_role = Role.objects.create(
            organization=self.org,
            name="Viewer",
            enabled=True,
            capabilities=[],
        )
        RoleAssignment.objects.create(
            user=self.member,
            organization=self.org,
            role=self.role,
            from_date=timezone.now().date(),
        )
        self.member = User.objects.select_related("profile").get(pk=self.member.pk)

    def test_backfill_adds_flag_to_selected_roles_only(self):
        from api.authenticate.services import (
            CAN_USE_CHAT_FLAG,
            FeatureFlagService,
            backfill_can_use_chat_on_roles,
        )

        stats = backfill_can_use_chat_on_roles(Role.objects.filter(pk=self.role.pk))
        self.assertEqual(stats["updated"], 1)
        self.assertEqual(stats["already_had"], 0)
        self.role.refresh_from_db()
        self.other_role.refresh_from_db()
        self.assertIn(CAN_USE_CHAT_FLAG, self.role.capabilities)
        self.assertNotIn(CAN_USE_CHAT_FLAG, self.other_role.capabilities)

        again = backfill_can_use_chat_on_roles(Role.objects.filter(pk=self.role.pk))
        self.assertEqual(again["updated"], 0)
        self.assertEqual(again["already_had"], 1)

        enabled, _ = FeatureFlagService.is_feature_enabled(
            CAN_USE_CHAT_FLAG, organization=self.org, user=self.member
        )
        self.assertTrue(enabled)
        enabled_invitee, _ = FeatureFlagService.is_feature_enabled(
            CAN_USE_CHAT_FLAG, user=self.invitee
        )
        self.assertFalse(enabled_invitee)

