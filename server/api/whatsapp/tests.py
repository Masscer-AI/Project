from unittest.mock import MagicMock, patch

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from api.authenticate.models import Organization, Token
from api.ai_layers.models import Agent
from api.messaging.models import Conversation, Message
from api.whatsapp.conversations import (
    get_or_create_whatsapp_conversation,
    tool_names_from_capabilities,
)
from api.whatsapp.models import WSNumber

User = get_user_model()


class WhatsappConversationBridgeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="wsowner", password="x")
        self.agent = Agent.objects.create(name="Test WA", salute="hi")
        self.ws = WSNumber.objects.create(
            user=self.user,
            agent=self.agent,
            number="1234567890",
            platform_id="pnid-test",
        )

    def test_get_or_create_unique(self):
        c1 = get_or_create_whatsapp_conversation(self.ws, "5491111222333")
        c2 = get_or_create_whatsapp_conversation(self.ws, "5491111222333")
        self.assertEqual(c1.id, c2.id)
        self.assertEqual(c1.whatsapp_user_number, "5491111222333")
        self.assertEqual(c1.ws_number_id, self.ws.id)
        self.assertIsNone(c1.user_id)

    def test_tool_names_from_capabilities_filters(self):
        caps = [
            {"name": "rag_query", "type": "internal_tool", "enabled": True},
            {"name": "not_a_real_tool", "type": "internal_tool", "enabled": True},
            {"name": "explore_web", "type": "internal_tool", "enabled": False},
        ]
        names = tool_names_from_capabilities(caps)
        self.assertIn("rag_query", names)
        self.assertNotIn("not_a_real_tool", names)
        self.assertNotIn("explore_web", names)

    def test_get_or_create_org_owned_without_ws_user(self):
        owner = User.objects.create_user(username="orgownerwa", password="x")
        org = Organization.objects.create(name="WA Org", owner=owner)
        ws = WSNumber.objects.create(
            user=None,
            organization=org,
            agent=self.agent,
            number="1234000000",
            platform_id="pnid-org-only",
        )
        conv = get_or_create_whatsapp_conversation(ws, "5491111222333")
        self.assertEqual(conv.organization_id, org.id)
        self.assertIsNone(conv.user_id)


class WhatsappWebhookEnqueueTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="wsowner2", password="x")
        self.agent = Agent.objects.create(name="Test WA2", salute="hi")
        self.ws = WSNumber.objects.create(
            user=self.user,
            agent=self.agent,
            number="0987654321",
            platform_id="pnid-enqueue",
        )

    @patch("api.whatsapp.actions.mark_message_as_read")
    @patch("api.whatsapp.tasks.whatsapp_conversation_agent_task")
    def test_handle_message_received_enqueues_task(self, mock_task, _mock_read):
        mock_task.delay = MagicMock()
        from api.whatsapp.actions import handle_message_received

        webhook_data = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "pnid-enqueue"},
                                "messages": [
                                    {
                                        "from": "5490000000000",
                                        "id": "wamid.inbound",
                                        "type": "text",
                                        "text": {"body": "Hello"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }
        message = webhook_data["entry"][0]["changes"][0]["value"]["messages"][0]
        handle_message_received(webhook_data, message)

        conv = Conversation.objects.get(
            ws_number=self.ws, whatsapp_user_number="5490000000000"
        )
        self.assertEqual(conv.whatsapp_last_inbound_wamid, "wamid.inbound")
        mock_task.delay.assert_called_once()
        kwargs = mock_task.delay.call_args.kwargs
        self.assertEqual(kwargs["conversation_id"], str(conv.id))
        self.assertEqual(kwargs["ws_number_id"], self.ws.id)
        self.assertEqual(kwargs["whatsapp_user_number"], "5490000000000")
        self.assertEqual(kwargs["inbound_wamid"], "wamid.inbound")
        self.assertIsNotNone(kwargs.get("regenerate_message_id"))
        stub = Message.objects.get(
            conversation=conv,
            type="user",
            metadata__whatsapp_inbound_wamid="wamid.inbound",
        )
        self.assertEqual(kwargs["regenerate_message_id"], stub.id)
        self.assertEqual(stub.text, ".")

    @patch("api.whatsapp.actions.mark_message_as_read")
    @patch("api.whatsapp.tasks.whatsapp_conversation_agent_task")
    def test_duplicate_inbound_wamid_skips_second_enqueue(self, mock_task, _mock_read):
        mock_task.delay = MagicMock()
        from api.whatsapp.actions import handle_message_received

        webhook_data = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "pnid-enqueue"},
                                "messages": [
                                    {
                                        "from": "5490000000000",
                                        "id": "wamid.dup",
                                        "type": "text",
                                        "text": {"body": "Once"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }
        message = webhook_data["entry"][0]["changes"][0]["value"]["messages"][0]
        handle_message_received(webhook_data, message)
        handle_message_received(webhook_data, message)
        self.assertEqual(mock_task.delay.call_count, 1)


@patch("api.whatsapp.views.FeatureFlagService.is_feature_enabled", return_value=(True, "on"))
class WhatsappNumbersManagementApiTests(TestCase):
    """Authenticated WhatsApp customization API (flag-gated; lines are provisioned in admin)."""

    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username="wa_mgmt_owner", password="x")
        self.org = Organization.objects.create(name="WA Mgmt Org", owner=self.owner)
        self.agent = Agent.objects.create(
            name="WA Org Agent",
            salute="hi",
            organization=self.org,
        )
        self.ws = WSNumber.objects.create(
            user=None,
            organization=self.org,
            agent=self.agent,
            number="15550001111",
            platform_id="pnid-mgmt",
            capabilities=[],
        )
        self.login_token, _ = Token.get_or_create(user=self.owner, token_type="login")

    def _auth_headers(self):
        return {"HTTP_AUTHORIZATION": f"Token {self.login_token.key}"}

    def test_get_numbers_returns_list_when_flag_on(self, _mock_ff):
        response = self.client.get("/v1/whatsapp/numbers", **self._auth_headers())
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["number"], "15550001111")

    def test_get_numbers_403_when_flag_off(self, mock_ff):
        mock_ff.return_value = (False, "off")
        response = self.client.get("/v1/whatsapp/numbers", **self._auth_headers())
        self.assertEqual(response.status_code, 403)

    def test_put_agent_rejects_inaccessible_agent(self, _mock_ff):
        other = User.objects.create_user(username="wa_other", password="x")
        alien = Agent.objects.create(name="Alien", salute="yo", user=other)
        response = self.client.put(
            f"/v1/whatsapp/numbers/{self.ws.number}",
            data=json.dumps({"slug": alien.slug}),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 403)

    def test_put_capabilities_validates_tool_names(self, _mock_ff):
        response = self.client.put(
            f"/v1/whatsapp/numbers/{self.ws.number}",
            data=json.dumps(
                {
                    "capabilities": [
                        {"name": "not_a_real_tool", "type": "internal_tool", "enabled": True}
                    ]
                }
            ),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn("details", body)

    def test_put_capabilities_persists_when_valid(self, _mock_ff):
        caps = [{"name": "rag_query", "type": "internal_tool", "enabled": True}]
        response = self.client.put(
            f"/v1/whatsapp/numbers/{self.ws.number}",
            data=json.dumps({"capabilities": caps}),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["capabilities"], caps)
        self.ws.refresh_from_db()
        self.assertEqual(self.ws.capabilities, caps)
