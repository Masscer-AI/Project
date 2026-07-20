import json

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from api.authenticate.models import (
    FeatureFlag,
    FeatureFlagAssignment,
    Organization,
    Token,
    UserProfile,
)


class OrganizationTimezoneUpdateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(
            username="orgowner",
            email="owner@test.com",
            password="owner-password-123",
        )
        self.manager = User.objects.create_user(
            username="orgmanager",
            email="manager@test.com",
            password="manager-password-123",
        )
        self.member = User.objects.create_user(
            username="orgmember",
            email="member@test.com",
            password="member-password-123",
        )
        self.org = Organization.objects.create(
            name="Acme Org",
            owner=self.owner,
            timezone="UTC",
        )
        UserProfile.objects.create(
            user=self.manager,
            organization=self.org,
            is_active=True,
        )
        UserProfile.objects.create(
            user=self.member,
            organization=self.org,
            is_active=True,
        )
        self.owner_token, _ = Token.get_or_create(user=self.owner, token_type="login")
        self.manager_token, _ = Token.get_or_create(user=self.manager, token_type="login")
        self.member_token, _ = Token.get_or_create(user=self.member, token_type="login")

    def _put_org(self, user_token, payload):
        return self.client.put(
            f"/v1/auth/organizations/{self.org.id}/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {user_token.key}",
        )

    def test_owner_can_update_timezone(self):
        response = self._put_org(
            self.owner_token,
            {
                "name": self.org.name,
                "description": "",
                "timezone": "America/New_York",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.org.refresh_from_db()
        self.assertEqual(self.org.timezone, "America/New_York")

    def test_manager_with_manage_flag_can_update_timezone(self):
        flag, _ = FeatureFlag.objects.get_or_create(
            name="manage-organization",
            defaults={"organization_only": False},
        )
        FeatureFlagAssignment.objects.create(
            user=self.manager,
            feature_flag=flag,
            enabled=True,
        )

        response = self._put_org(
            self.manager_token,
            {
                "name": self.org.name,
                "description": "",
                "timezone": "Europe/Madrid",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.org.refresh_from_db()
        self.assertEqual(self.org.timezone, "Europe/Madrid")

    def test_member_without_manage_flag_cannot_update(self):
        response = self._put_org(
            self.member_token,
            {
                "name": self.org.name,
                "description": "",
                "timezone": "Europe/Madrid",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.org.refresh_from_db()
        self.assertEqual(self.org.timezone, "UTC")

    def test_invalid_timezone_rejected(self):
        response = self._put_org(
            self.owner_token,
            {
                "name": self.org.name,
                "description": "",
                "timezone": "Not/A_Timezone",
            },
        )
        self.assertEqual(response.status_code, 400)
