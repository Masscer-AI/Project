from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from api.authenticate.models import (
    Organization,
    OrganizationInvite,
    hash_organization_invite_token,
)
from api.ai_layers.models import Agent, LanguageModel
from api.consumption.models import Currency
from api.providers.models import AIProvider
from api.whatsapp.models import WSNumber


class OrganizationInviteAdminTests(TestCase):
    def setUp(self):
        Currency.objects.get_or_create(
            name="Compute Unit", defaults={"one_usd_is": 1000}
        )
        provider = AIProvider.objects.create(name="OpenAI-invite-admin")
        self.llm = LanguageModel.objects.create(
            provider=provider, slug="gpt-invite-admin", name="GPT Invite Admin"
        )
        self.staff = User.objects.create_user(
            "invite-admin-staff",
            "invite-admin-staff@example.com",
            "pw-test-123",
            is_staff=True,
            is_superuser=True,
        )
        self.owner = User.objects.create_user(
            "invite-admin-owner",
            "invite-admin-owner@example.com",
            "pw-test-123",
        )
        self.member = User.objects.create_user(
            "invite-admin-member",
            "invite-admin-member@example.com",
            "pw-test-123",
        )
        self.org = Organization.objects.create(name="Invite Admin Org", owner=self.owner)
        self.agent = Agent.objects.create(
            name="FernandAI",
            salute="hi",
            organization=self.org,
            user=self.owner,
            llm=self.llm,
            model_slug=self.llm.slug,
        )
        self.line = WSNumber.objects.create(
            organization=self.org,
            agent=self.agent,
            number="525511112222",
            platform_id="pnid-invite-admin",
        )
        self.client = Client()
        self.client.force_login(self.staff)
        self.changelist = reverse("admin:authenticate_organizationinvite_changelist")

    def _invite(self, *, email, status, send_welcome=True, phones=None, line_ids=None, user=None):
        return OrganizationInvite.objects.create(
            organization=self.org,
            email=email,
            name="Maria",
            invited_by=self.owner,
            token_hash=hash_organization_invite_token(email),
            status=status,
            invite_expires_at=timezone.now() + timedelta(days=7),
            accepted_user=user,
            send_welcome_message=send_welcome,
            welcome_phones=phones if phones is not None else ["525511112222"],
            welcome_line_ids=line_ids if line_ids is not None else [self.line.id],
            welcome_help_text="Paying your bills.",
            welcome_language="en",
        )

    def _post_action(self, *invites):
        return self.client.post(
            self.changelist,
            {
                "action": "resend_welcome_whatsapp",
                "_selected_action": [str(invite.pk) for invite in invites],
            },
            follow=True,
        )

    @patch("api.authenticate.tasks.send_invite_welcome_whatsapp.delay")
    def test_resend_action_queues_accepted_welcome(self, delay_mock):
        invite = self._invite(
            email="accepted@example.com",
            status=OrganizationInvite.Status.ACCEPTED,
            user=self.member,
        )
        response = self._post_action(invite)
        self.assertEqual(response.status_code, 200)
        delay_mock.assert_called_once_with(str(invite.id))
        self.assertContains(response, "Queued the welcome WhatsApp for accepted@example.com")

    @patch("api.authenticate.tasks.send_invite_welcome_whatsapp.delay")
    def test_resend_action_skips_invite_before_signup(self, delay_mock):
        invite = self._invite(
            email="pending@example.com",
            status=OrganizationInvite.Status.PENDING,
        )
        response = self._post_action(invite)
        self.assertEqual(response.status_code, 200)
        delay_mock.assert_not_called()
        self.assertContains(response, "the person has not finished signup")
