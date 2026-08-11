from django.contrib.auth.models import User
from django.test import Client, TestCase

from api.ai_layers.models import LanguageModel
from api.authenticate.models import Organization, Role, Token, UserProfile
from api.consumption.models import Currency
from api.providers.models import AIProvider


class OrganizationRolesListAccessTests(TestCase):
    def setUp(self):
        Currency.objects.get_or_create(
            name="Compute Unit", defaults={"one_usd_is": 1000}
        )
        provider = AIProvider.objects.create(name="OpenAI")
        LanguageModel.objects.create(
            provider=provider,
            name="Test LLM",
            slug="test-llm-roles-list",
        )
        self.client = Client()
        self.owner = User.objects.create_user(username="roles-owner", password="x")
        self.member = User.objects.create_user(username="roles-member", password="x")
        self.outsider = User.objects.create_user(username="roles-outsider", password="x")
        self.org = Organization.objects.create(name="Roles Org", owner=self.owner)
        UserProfile.objects.filter(user=self.member).update(organization=self.org)
        self.member = User.objects.select_related("profile").get(pk=self.member.pk)
        self.role = Role.objects.create(
            organization=self.org,
            name="Analysts",
            capabilities=["train-agents"],
        )
        self.owner_token = Token.objects.create(user=self.owner, token_type="permanent")
        self.member_token = Token.objects.create(user=self.member, token_type="permanent")
        self.outsider_token = Token.objects.create(
            user=self.outsider, token_type="permanent"
        )

    def _auth(self, token: Token):
        return {"HTTP_AUTHORIZATION": f"Token {token.key}"}

    def test_member_can_list_roles(self):
        resp = self.client.get(
            f"/v1/auth/organizations/{self.org.id}/roles/",
            **self._auth(self.member_token),
        )
        self.assertEqual(resp.status_code, 200)
        names = {r["name"] for r in resp.json()}
        self.assertIn("Analysts", names)

    def test_member_cannot_create_role(self):
        resp = self.client.post(
            f"/v1/auth/organizations/{self.org.id}/roles/",
            data='{"name": "NewRole"}',
            content_type="application/json",
            **self._auth(self.member_token),
        )
        self.assertEqual(resp.status_code, 403)

    def test_outsider_cannot_list_roles(self):
        resp = self.client.get(
            f"/v1/auth/organizations/{self.org.id}/roles/",
            **self._auth(self.outsider_token),
        )
        self.assertEqual(resp.status_code, 403)
