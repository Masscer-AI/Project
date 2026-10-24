import json

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from api.ai_layers.models import LanguageModel
from api.authenticate.models import (
    FeatureFlag,
    FeatureFlagAssignment,
    Organization,
    Token,
    UserProfile,
)
from api.consumption.models import Currency
from api.messaging.models import Conversation, ConversationAlert, ConversationAlertRule
from api.providers.models import AIProvider


def _bootstrap():
    Currency.objects.get_or_create(name="Compute Unit", defaults={"one_usd_is": 1000})
    provider, _ = AIProvider.objects.get_or_create(name="Alert Access Provider")
    LanguageModel.objects.get_or_create(
        slug="alert-access-model",
        defaults={"provider": provider, "name": "Alert Access Model"},
    )


class AlertAccessTests(TestCase):
    def setUp(self):
        _bootstrap()
        self.client = APIClient()
        self.owner = User.objects.create_user(username="alert-owner", password="x")
        self.member = User.objects.create_user(username="alert-member", password="x")
        self.org = Organization.objects.create(name="Alert Org", owner=self.owner)
        UserProfile.objects.filter(user=self.member).update(
            organization=self.org, is_active=True
        )
        rule = ConversationAlertRule.objects.create(
            name="Angry customer", trigger="Customer is angry", organization=self.org
        )
        conversation = Conversation.objects.create(
            user=self.owner, organization=self.org, title="Chat"
        )
        self.alert = ConversationAlert.objects.create(
            title="Angry", conversation=conversation, alert_rule=rule
        )

    def _auth(self, user):
        token = Token.objects.create(user=user)
        return {"HTTP_AUTHORIZATION": f"Token {token.key}"}

    def _grant(self, user, flag_name):
        flag, _ = FeatureFlag.objects.get_or_create(name=flag_name)
        FeatureFlagAssignment.objects.create(user=user, feature_flag=flag, enabled=True)

    def test_member_without_flag_cannot_list_alerts(self):
        response = self.client.get("/v1/messaging/alerts", **self._auth(self.member))
        self.assertEqual(response.status_code, 403)

    def test_member_without_flag_cannot_see_alert_stats(self):
        response = self.client.get("/v1/messaging/alerts/stats/", **self._auth(self.member))
        self.assertEqual(response.status_code, 403)

    def test_member_without_flag_cannot_resolve_alert(self):
        response = self.client.put(
            f"/v1/messaging/alerts/{self.alert.id}/",
            data=json.dumps({"status": "RESOLVED"}),
            content_type="application/json",
            **self._auth(self.member),
        )
        self.assertEqual(response.status_code, 403)
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.status, "PENDING")

    def test_member_with_flag_can_list_alerts(self):
        self._grant(self.member, "view-alerts")
        response = self.client.get("/v1/messaging/alerts", **self._auth(self.member))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([a["id"] for a in response.json()], [str(self.alert.id)])

    def test_owner_can_list_alerts(self):
        response = self.client.get("/v1/messaging/alerts", **self._auth(self.owner))
        self.assertEqual(response.status_code, 200)

    def test_notification_rules_need_alert_rules_manager(self):
        response = self.client.get("/v1/notify/notification-rules/", **self._auth(self.member))
        self.assertEqual(response.status_code, 403)

        self._grant(self.member, "alert-rules-manager")
        response = self.client.get("/v1/notify/notification-rules/", **self._auth(self.member))
        self.assertEqual(response.status_code, 200)

    def test_any_member_can_read_own_notifications(self):
        response = self.client.get("/v1/notify/my-notifications/", **self._auth(self.member))
        self.assertEqual(response.status_code, 200)
