from unittest.mock import MagicMock, patch

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from api.authenticate.models import Organization, Token
from api.ai_layers.models import Agent
from api.messaging.models import Conversation, Message, MessageAttachment
from api.whatsapp.capability_tools import WHATSAPP_REQUIRED_CAPABILITY_TOOLS
from api.whatsapp.conversations import (
    get_or_create_whatsapp_conversation,
    tool_names_from_capabilities,
)
from api.whatsapp.models import WSContact, WSNumber


def _required_capability_entries() -> list[dict]:
    return [
        {"name": name, "type": "internal_tool", "enabled": True}
        for name in WHATSAPP_REQUIRED_CAPABILITY_TOOLS
    ]

User = get_user_model()


class WhatsappConversationBridgeTests(TestCase):
    def setUp(self):
        from api.ai_layers.models import LanguageModel
        from api.consumption.models import Currency
        from api.providers.models import AIProvider

        Currency.objects.get_or_create(
            name="Compute Unit", defaults={"one_usd_is": 1000}
        )
        provider = AIProvider.objects.create(name="OpenAI-wa-bridge")
        LanguageModel.objects.create(
            provider=provider, slug="gpt-wa-bridge", name="GPT WA Bridge"
        )
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
        self.assertIsNotNone(c1.ws_contact_id)
        self.assertEqual(c1.ws_contact.number, "5491111222333")
        self.assertIsNone(c1.ws_contact.user_id)
        self.assertEqual(c2.ws_contact_id, c1.ws_contact_id)

    def test_tool_names_from_capabilities_filters(self):
        caps = [
            {"name": "rag_query", "type": "internal_tool", "enabled": True},
            {"name": "not_a_real_tool", "type": "internal_tool", "enabled": True},
            {"name": "explore_web", "type": "internal_tool", "enabled": False},
            {"name": "read_plugin_instructions", "type": "internal_tool", "enabled": True},
            {"name": "send_email", "type": "internal_tool", "enabled": True},
        ]
        names = tool_names_from_capabilities(caps)
        self.assertIn("rag_query", names)
        self.assertIn("read_attachment", names)
        self.assertIn("list_attachments", names)
        self.assertIn("read_plugin_instructions", names)
        # Unlinked visitor: USER_REQUIRED tools are stripped.
        self.assertNotIn("send_email", names)
        self.assertNotIn("list_conversations", names)
        self.assertNotIn("not_a_real_tool", names)
        self.assertNotIn("explore_web", names)

        linked = tool_names_from_capabilities(
            caps
            + [
                {
                    "name": "list_conversations",
                    "type": "internal_tool",
                    "enabled": True,
                }
            ],
            user=self.user,
        )
        self.assertIn("send_email", linked)
        self.assertIn("list_conversations", linked)
        self.assertIn("rag_query", linked)

    def test_generate_document_file_allowed_on_whatsapp(self):
        caps = [
            {
                "name": "generate_document_file",
                "type": "internal_tool",
                "enabled": True,
            },
        ]
        names = tool_names_from_capabilities(caps)
        self.assertIn("generate_document_file", names)

    def test_tool_names_from_capabilities_forces_required_when_disabled(self):
        caps = [
            {"name": "read_attachment", "type": "internal_tool", "enabled": False},
            {"name": "list_attachments", "type": "internal_tool", "enabled": False},
        ]
        names = tool_names_from_capabilities(caps)
        for required_name in WHATSAPP_REQUIRED_CAPABILITY_TOOLS:
            self.assertIn(required_name, names)

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

    def test_inactive_thread_allows_new_active_same_phone(self):
        from api.whatsapp.conversations import create_whatsapp_conversation

        c1 = get_or_create_whatsapp_conversation(self.ws, "5492222333444")
        c1.status = "inactive"
        c1.save(update_fields=["status", "updated_at"])
        c2 = create_whatsapp_conversation(self.ws, "5492222333444")
        self.assertEqual(c2.status, "active")
        self.assertNotEqual(c1.id, c2.id)
        c3 = get_or_create_whatsapp_conversation(self.ws, "5492222333444")
        self.assertEqual(c3.id, c2.id)


class WhatsappClearCommandTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        from api.ai_layers.models import LanguageModel
        from api.consumption.models import Currency
        from api.providers.models import AIProvider

        cache.clear()
        Currency.objects.get_or_create(
            name="Compute Unit", defaults={"one_usd_is": 1000}
        )
        provider = AIProvider.objects.create(name="OpenAI-wa-clear")
        LanguageModel.objects.create(
            provider=provider, slug="gpt-wa-clear", name="GPT WA Clear"
        )
        self.user = User.objects.create_user(username="wsclear", password="x")
        self.agent = Agent.objects.create(name="Test WA Clear", salute="hi")
        self.ws = WSNumber.objects.create(
            user=self.user,
            agent=self.agent,
            number="5550001111",
            platform_id="pnid-clear",
        )

    def test_is_clear_command(self):
        from api.whatsapp.inbound import is_clear_command

        self.assertTrue(is_clear_command("/clear"))
        self.assertTrue(is_clear_command("  /clear  "))
        self.assertFalse(is_clear_command("/CLEAR"))
        self.assertFalse(is_clear_command("hello"))

    @patch("api.whatsapp.actions.send_message")
    def test_clear_deactivates_and_creates_new_active(self, mock_send):
        from api.whatsapp.inbound import (
            WHATSAPP_CLEAR_REPLY,
            process_text_inbound,
        )

        mock_send.return_value = "wamid-clear-out"
        conv = get_or_create_whatsapp_conversation(self.ws, "5493333444555")
        process_text_inbound(
            ws_number=self.ws,
            conversation=conv,
            user_phone="5493333444555",
            inbound_wamid="wamid-clear-1",
            body="/clear",
        )
        conv.refresh_from_db()
        self.assertEqual(conv.status, "inactive")

        new_conv = get_or_create_whatsapp_conversation(self.ws, "5493333444555")
        self.assertNotEqual(new_conv.id, conv.id)
        self.assertEqual(new_conv.status, "active")
        self.assertEqual(new_conv.whatsapp_last_inbound_wamid, "wamid-clear-1")

        mock_send.assert_called_once()
        self.assertEqual(
            mock_send.call_args[0][2],
            WHATSAPP_CLEAR_REPLY,
        )
        self.assertFalse(
            Message.objects.filter(
                conversation=new_conv,
                type="assistant",
            ).exists()
        )

    @patch("api.whatsapp.actions.send_message", return_value="wamid-clear-out")
    @patch("api.whatsapp.inbound.enqueue_whatsapp_inbound_agent")
    def test_clear_skips_agent_enqueue(self, mock_enqueue, _mock_send):
        from api.whatsapp.inbound import process_text_inbound

        conv = get_or_create_whatsapp_conversation(self.ws, "5494444555666")
        process_text_inbound(
            ws_number=self.ws,
            conversation=conv,
            user_phone="5494444555666",
            inbound_wamid="wamid-clear-2",
            body="/clear",
        )
        mock_enqueue.assert_not_called()

    @patch("api.whatsapp.actions.send_message", return_value="wamid-clear-out")
    @patch("api.whatsapp.tasks.whatsapp_flush_inbound_agent_task.apply_async")
    @patch("api.whatsapp.actions.mark_message_as_read")
    def test_handle_message_received_clear_skips_flush(
        self, _mock_read, mock_apply_async, _mock_send
    ):
        from api.whatsapp.actions import handle_message_received

        webhook_data = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "pnid-clear"},
                                "messages": [
                                    {
                                        "from": "5495555666777",
                                        "id": "wamid.clear.webhook",
                                        "type": "text",
                                        "text": {"body": "/clear"},
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

        mock_apply_async.assert_not_called()
        active = Conversation.objects.get(
            ws_number=self.ws,
            whatsapp_user_number="5495555666777",
            status="active",
        )
        self.assertEqual(active.whatsapp_last_inbound_wamid, "wamid.clear.webhook")


class WhatsappWebhookEnqueueTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        from api.ai_layers.models import LanguageModel
        from api.consumption.models import Currency
        from api.providers.models import AIProvider

        cache.clear()
        Currency.objects.get_or_create(
            name="Compute Unit", defaults={"one_usd_is": 1000}
        )
        provider = AIProvider.objects.create(name="OpenAI-wa-enqueue")
        LanguageModel.objects.create(
            provider=provider, slug="gpt-wa-enqueue", name="GPT WA Enqueue"
        )
        self.user = User.objects.create_user(username="wsowner2", password="x")
        self.agent = Agent.objects.create(name="Test WA2", salute="hi")
        self.ws = WSNumber.objects.create(
            user=self.user,
            agent=self.agent,
            number="0987654321",
            platform_id="pnid-enqueue",
        )

    @patch("api.whatsapp.actions.mark_message_as_read")
    @patch("api.whatsapp.tasks.whatsapp_flush_inbound_agent_task.apply_async")
    def test_handle_message_received_enqueues_task(self, mock_apply_async, _mock_read):
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
            ws_number=self.ws,
            whatsapp_user_number="5490000000000",
            status="active",
        )
        self.assertEqual(conv.whatsapp_last_inbound_wamid, "wamid.inbound")
        mock_apply_async.assert_called_once()
        kwargs = mock_apply_async.call_args.kwargs["kwargs"]
        self.assertEqual(mock_apply_async.call_args.kwargs["countdown"], 3)
        self.assertEqual(kwargs["conversation_id"], str(conv.id))
        self.assertEqual(kwargs["ws_number_id"], self.ws.id)
        self.assertEqual(kwargs["whatsapp_user_number"], "5490000000000")
        stub = Message.objects.get(
            conversation=conv,
            type="user",
            metadata__whatsapp_inbound_wamid="wamid.inbound",
        )
        # Stub shows inbound text preview while debounce/agent flush is pending.
        self.assertEqual(stub.text, "Hello")

    @patch("api.whatsapp.actions.mark_message_as_read")
    @patch("api.whatsapp.tasks.whatsapp_flush_inbound_agent_task.apply_async")
    def test_duplicate_inbound_wamid_skips_second_enqueue(self, mock_apply_async, _mock_read):
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
        self.assertEqual(mock_apply_async.call_count, 1)

    @patch("api.whatsapp.inbound.fetch_whatsapp_media_bytes")
    @patch("api.whatsapp.actions.mark_message_as_read")
    @patch("api.whatsapp.tasks.whatsapp_flush_inbound_agent_task.apply_async")
    def test_handle_document_message_enqueues_task_with_attachment(
        self, mock_apply_async, _mock_read, mock_fetch_media
    ):
        mock_fetch_media.return_value = (b"%PDF-1.4 test", "application/pdf")
        from api.whatsapp.actions import handle_webhook

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
                                        "id": "wamid.doc.inbound",
                                        "type": "document",
                                        "document": {
                                            "id": "media-doc-1",
                                            "url": "https://lookaside.fbsbx.com/whatsapp_business/attachments/?id=1",
                                            "filename": "test.pdf",
                                            "mime_type": "application/pdf",
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }
        handle_webhook(webhook_data)

        conv = Conversation.objects.get(
            ws_number=self.ws,
            whatsapp_user_number="5490000000000",
            status="active",
        )
        mock_apply_async.assert_called_once()
        kwargs = mock_apply_async.call_args.kwargs["kwargs"]
        self.assertEqual(kwargs["conversation_id"], str(conv.id))
        stub = Message.objects.get(
            conversation=conv,
            type="user",
            metadata__whatsapp_inbound_wamid="wamid.doc.inbound",
        )
        from django.core.cache import cache
        from api.whatsapp.inbound import whatsapp_inbound_buffer_key

        buffered = cache.get(whatsapp_inbound_buffer_key(str(conv.id))) or []
        self.assertEqual(len(buffered), 1)
        user_inputs = buffered[0]["user_inputs"]
        self.assertEqual(user_inputs[0]["type"], "input_text")
        self.assertEqual(user_inputs[1]["type"], "input_attachment")
        att = MessageAttachment.objects.get(id=user_inputs[1]["attachment_id"])
        self.assertEqual(att.conversation_id, conv.id)
        self.assertEqual(att.content_type, "application/pdf")
        self.assertEqual(buffered[0]["regenerate_message_id"], stub.id)

    @patch("api.whatsapp.tasks.whatsapp_conversation_agent_task")
    def test_flush_task_merges_buffered_inbounds(self, mock_agent_task):
        from django.core.cache import cache

        from api.whatsapp.inbound import (
            whatsapp_inbound_buffer_key,
            whatsapp_inbound_schedule_lock_key,
        )
        from api.whatsapp.tasks import whatsapp_flush_inbound_agent_task

        conv = Conversation.objects.create(
            user=None,
            ws_number=self.ws,
            whatsapp_user_number="5490000000001",
        )
        first = Message.objects.create(
            conversation=conv,
            type="user",
            text=".",
            metadata={"whatsapp_inbound_wamid": "wamid.1"},
        )
        second = Message.objects.create(
            conversation=conv,
            type="user",
            text=".",
            metadata={"whatsapp_inbound_wamid": "wamid.2"},
        )
        cache.set(
            whatsapp_inbound_buffer_key(str(conv.id)),
            [
                {
                    "inbound_wamid": "wamid.1",
                    "user_inputs": [{"type": "input_text", "text": "Hello"}],
                    "regenerate_message_id": first.id,
                },
                {
                    "inbound_wamid": "wamid.2",
                    "user_inputs": [{"type": "input_text", "text": "there"}],
                    "regenerate_message_id": second.id,
                },
            ],
            timeout=120,
        )
        cache.set(whatsapp_inbound_schedule_lock_key(str(conv.id)), True, timeout=120)

        whatsapp_flush_inbound_agent_task(
            conversation_id=str(conv.id),
            ws_number_id=self.ws.id,
            whatsapp_user_number="5490000000001",
        )

        mock_agent_task.assert_called_once_with(
            conversation_id=str(conv.id),
            user_inputs=[
                {"type": "input_text", "text": "Hello"},
                {"type": "input_text", "text": "there"},
            ],
            ws_number_id=self.ws.id,
            whatsapp_user_number="5490000000001",
            inbound_wamid="wamid.2",
            regenerate_message_id=first.id,
        )

    @patch("api.whatsapp.actions.handle_message_received")
    @patch("api.whatsapp.actions.transcribe_audio", return_value="Hola desde audio")
    @patch("api.whatsapp.actions.download_audio", return_value="/tmp/fake.ogg")
    def test_handle_audio_message_transcribes_and_forwards_as_text(
        self, _mock_download, _mock_transcribe, mock_handle_message
    ):
        from api.whatsapp.actions import handle_audio_message

        webhook_data = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "pnid-enqueue"},
                            }
                        }
                    ]
                }
            ]
        }
        message = {
            "from": "5490000000000",
            "id": "wamid.audio.inbound",
            "type": "audio",
            "audio": {"id": "media-audio-1"},
        }

        handle_audio_message(webhook_data, message)

        mock_handle_message.assert_called_once()
        forwarded = mock_handle_message.call_args.args[1]
        self.assertEqual(forwarded["id"], "wamid.audio.inbound")
        self.assertEqual(forwarded["type"], "text")
        self.assertEqual(forwarded["text"]["body"], "Hola desde audio")

    @patch("api.whatsapp.actions.handle_message_received")
    def test_handle_interactive_button_reply_forwards_as_text(
        self, mock_handle_message
    ):
        from api.whatsapp.actions import handle_interactive_message, handle_webhook

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
                                        "id": "wamid.interactive.yes",
                                        "type": "interactive",
                                        "interactive": {
                                            "type": "button_reply",
                                            "button_reply": {
                                                "id": "approve",
                                                "title": "Yes, permission granted",
                                            },
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }
        message = webhook_data["entry"][0]["changes"][0]["value"]["messages"][0]
        handle_interactive_message(webhook_data, message)

        mock_handle_message.assert_called_once()
        forwarded = mock_handle_message.call_args.args[1]
        self.assertEqual(forwarded["id"], "wamid.interactive.yes")
        self.assertEqual(forwarded["type"], "text")
        self.assertEqual(forwarded["text"]["body"], "Yes, permission granted")

        mock_handle_message.reset_mock()
        handle_webhook(webhook_data)
        mock_handle_message.assert_called_once()

    @patch("api.whatsapp.actions.handle_message_received")
    def test_handle_legacy_button_reply_forwards_as_text(self, mock_handle_message):
        from api.whatsapp.actions import handle_button_message, handle_webhook

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
                                        "id": "wamid.button.yes",
                                        "type": "button",
                                        "button": {
                                            "text": "Si, permiso concedido.",
                                            "payload": "approve",
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }
        message = webhook_data["entry"][0]["changes"][0]["value"]["messages"][0]
        handle_button_message(webhook_data, message)

        mock_handle_message.assert_called_once()
        forwarded = mock_handle_message.call_args.args[1]
        self.assertEqual(forwarded["text"]["body"], "Si, permiso concedido.")

        mock_handle_message.reset_mock()
        handle_webhook(webhook_data)
        mock_handle_message.assert_called_once()


@patch("api.whatsapp.views.FeatureFlagService.is_feature_enabled", return_value=(True, "on"))
class WhatsappNumbersManagementApiTests(TestCase):
    """Authenticated WhatsApp customization API (flag-gated; lines are provisioned in admin)."""

    def setUp(self):
        from api.ai_layers.models import LanguageModel
        from api.consumption.models import Currency
        from api.providers.models import AIProvider

        Currency.objects.get_or_create(
            name="Compute Unit", defaults={"one_usd_is": 1000}
        )
        provider = AIProvider.objects.create(name="OpenAI-wa-mgmt")
        LanguageModel.objects.create(
            provider=provider, slug="gpt-wa-mgmt", name="GPT WA Mgmt"
        )
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

    def test_put_capabilities_accepts_any_registered_tool(self, _mock_ff):
        response = self.client.put(
            f"/v1/whatsapp/numbers/{self.ws.number}",
            data=json.dumps(
                {
                    "capabilities": [
                        {
                            "name": "read_plugin_instructions",
                            "type": "internal_tool",
                            "enabled": True,
                        },
                        {
                            "name": "generate_excel_file",
                            "type": "internal_tool",
                            "enabled": True,
                        },
                        {
                            "name": "send_email",
                            "type": "internal_tool",
                            "enabled": True,
                        },
                    ]
                }
            ),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 200)
        names = {c["name"] for c in response.json()["capabilities"] if c.get("enabled")}
        self.assertIn("read_plugin_instructions", names)
        self.assertIn("generate_excel_file", names)
        self.assertIn("send_email", names)

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
        expected = [
            {"name": "rag_query", "type": "internal_tool", "enabled": True},
            *_required_capability_entries(),
        ]
        self.assertEqual(response.json()["capabilities"], expected)
        self.ws.refresh_from_db()
        self.assertEqual(self.ws.capabilities, expected)

    def test_put_capabilities_forces_required_tools_enabled(self, _mock_ff):
        caps = [
            {"name": "read_attachment", "type": "internal_tool", "enabled": False},
            {"name": "list_attachments", "type": "internal_tool", "enabled": False},
        ]
        response = self.client.put(
            f"/v1/whatsapp/numbers/{self.ws.number}",
            data=json.dumps({"capabilities": caps}),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["capabilities"],
            _required_capability_entries(),
        )

    def test_list_and_link_contacts(self, _mock_ff):
        from api.authenticate.models import UserProfile

        member = User.objects.create_user(
            username="wa_link_member", email="link@example.com", password="x"
        )
        profile = UserProfile.objects.get(user=member)
        profile.organization = self.org
        profile.is_active = True
        profile.save()

        contact = WSContact.objects.create(
            ws_number=self.ws, number="15550009999"
        )

        list_resp = self.client.get(
            f"/v1/whatsapp/numbers/{self.ws.id}/contacts",
            **self._auth_headers(),
        )
        self.assertEqual(list_resp.status_code, 200)
        data = list_resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["number"], "15550009999")
        self.assertIsNone(data[0]["user_id"])

        link_resp = self.client.patch(
            f"/v1/whatsapp/contacts/{contact.id}",
            data=json.dumps({"user_id": member.id}),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(link_resp.status_code, 200)
        self.assertEqual(link_resp.json()["user_id"], member.id)
        contact.refresh_from_db()
        self.assertEqual(contact.user_id, member.id)

        unlink_resp = self.client.patch(
            f"/v1/whatsapp/contacts/{contact.id}",
            data=json.dumps({"user_id": None}),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(unlink_resp.status_code, 200)
        self.assertIsNone(unlink_resp.json()["user_id"])

    def test_link_contact_rejects_non_member(self, _mock_ff):
        outsider = User.objects.create_user(
            username="wa_outsider", email="out@example.com", password="x"
        )
        contact = WSContact.objects.create(
            ws_number=self.ws, number="15550008888"
        )
        resp = self.client.patch(
            f"/v1/whatsapp/contacts/{contact.id}",
            data=json.dumps({"user_id": outsider.id}),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(resp.status_code, 400)


@patch("api.authenticate.services.FeatureFlagService.is_feature_enabled")
class WhatsappEmbeddedMediaToolTests(TestCase):
    """WhatsApp lines gate create_image / create_speech via capabilities, not app feature flags."""

    def setUp(self):
        from api.ai_layers.models import LanguageModel
        from api.consumption.models import Currency
        from api.providers.models import AIProvider

        Currency.objects.get_or_create(name="Compute Unit", defaults={"one_usd_is": 1000})
        provider = AIProvider.objects.create(name="OpenAI-wa-media")
        llm = LanguageModel.objects.create(
            provider=provider, slug="gpt-wa-media", name="GPT WA Media"
        )
        self.owner = User.objects.create_user(username="wa_media_owner", password="x")
        self.org = Organization.objects.create(name="WA Media Org", owner=self.owner)
        self.agent = Agent.objects.create(
            name="WA Media Agent",
            salute="hi",
            organization=self.org,
            llm=llm,
            model_slug=llm.slug,
            model_provider="openai",
        )
        self.ws = WSNumber.objects.create(
            user=None,
            organization=self.org,
            agent=self.agent,
            number="15550002222",
            platform_id="pnid-media",
            capabilities=[
                {"name": "create_image", "type": "internal_tool", "enabled": True},
            ],
        )

    @patch("api.ai_layers.tools.create_image.OpenAI")
    def test_create_image_skips_image_tools_flag_for_whatsapp_conversation(
        self, openai_cls_mock, is_feature_enabled_mock
    ):
        from api.ai_layers.tools.create_image import _create_image_impl
        from api.whatsapp.conversations import get_or_create_whatsapp_conversation

        is_feature_enabled_mock.return_value = (False, "off")
        conv = get_or_create_whatsapp_conversation(self.ws, "5939000000001")

        client_inst = MagicMock()
        openai_cls_mock.return_value = client_inst
        img_obj = MagicMock(
            b64_json="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
        client_inst.images.generate.return_value = MagicMock(data=[img_obj])

        result = _create_image_impl(
            prompt="cat shrimp fusion",
            model="gpt-image-2",
            aspect_ratio="square",
            guidance_attachments=[],
            conversation_id=str(conv.id),
            user_id=None,
            agent_slug=self.agent.slug,
        )

        is_feature_enabled_mock.assert_not_called()
        self.assertEqual(result.model, "gpt-image-2")

    @patch("api.ai_layers.tools.create_speech.synthesize_speech_bytes", return_value=(b"fake-audio", "gpt-4o-mini-tts"))
    def test_create_speech_skips_chat_generate_speech_flag_for_whatsapp_conversation(
        self, _tts_mock, is_feature_enabled_mock
    ):
        from api.ai_layers.tools.create_speech import _create_speech_impl
        from api.whatsapp.conversations import get_or_create_whatsapp_conversation

        is_feature_enabled_mock.return_value = (False, "off")
        conv = get_or_create_whatsapp_conversation(self.ws, "5939000000002")

        result = _create_speech_impl(
            text="hello",
            voice_id=None,
            instructions="",
            output_format="mp3",
            conversation_id=str(conv.id),
            user_id=None,
            agent_slug=self.agent.slug,
        )

        is_feature_enabled_mock.assert_not_called()
        self.assertEqual(result.output_format, "mp3")

    @patch("api.ai_layers.tools.generate_video._generate_video_veo")
    def test_generate_video_skips_video_tools_flag_for_whatsapp_conversation(
        self, veo_mock, is_feature_enabled_mock
    ):
        from api.ai_layers.tools.generate_video import _generate_video_impl
        from api.whatsapp.conversations import get_or_create_whatsapp_conversation

        is_feature_enabled_mock.return_value = (False, "off")
        conv = get_or_create_whatsapp_conversation(self.ws, "5939000000003")
        veo_mock.return_value = (b"fake-mp4-bytes", 8.0)

        result = _generate_video_impl(
            prompt="ocean waves at sunset",
            image_attachment_id="",
            aspect_ratio="landscape",
            conversation_id=str(conv.id),
            user_id=None,
            agent_slug=self.agent.slug,
        )

        is_feature_enabled_mock.assert_not_called()
        self.assertEqual(result.duration_seconds, 8.0)


class WhatsappOutboundMediaHelperTests(TestCase):
    def test_whatsapp_media_type_mapping(self):
        from django.core.files.base import ContentFile

        from api.messaging.models import MessageAttachment
        from api.whatsapp.outbound_media import whatsapp_media_type_for_attachment

        img = MessageAttachment(kind="file", content_type="image/png")
        img.file = ContentFile(b"x", name="test.png")
        self.assertEqual(whatsapp_media_type_for_attachment(img), "image")

        aud = MessageAttachment(
            kind="file", content_type="audio/mpeg"
        )
        aud.file = ContentFile(b"x", name="speech.mp3")
        self.assertEqual(whatsapp_media_type_for_attachment(aud), "audio")

    def test_absolute_file_url_uses_api_base(self):
        from django.core.files.base import ContentFile
        from django.test import override_settings

        from api.messaging.attachment_urls import absolute_file_url_for_attachment
        from api.messaging.models import MessageAttachment

        att = MessageAttachment(kind="file", content_type="image/png")
        att.file = ContentFile(b"x", name="message_attachments/2026/05/x.png")
        with override_settings(API_BASE_URL="https://api.example.com", MEDIA_URL="/media/"):
            url = absolute_file_url_for_attachment(att)
        self.assertEqual(
            url,
            "https://api.example.com/media/message_attachments/2026/05/x.png",
        )


class WhatsappDeliverReplyTests(TestCase):
    def setUp(self):
        from api.ai_layers.models import LanguageModel
        from api.consumption.models import Currency
        from api.providers.models import AIProvider

        Currency.objects.get_or_create(
            name="Compute Unit", defaults={"one_usd_is": 1000}
        )
        provider = AIProvider.objects.create(name="OpenAI-wa-deliver")
        LanguageModel.objects.create(
            provider=provider, slug="gpt-wa-deliver", name="GPT WA Deliver"
        )
        self.owner = User.objects.create_user(username="wa_deliver_owner", password="x")
        self.org = Organization.objects.create(name="WA Deliver Org", owner=self.owner)
        self.agent = Agent.objects.create(
            name="WA Deliver Agent",
            salute="hi",
            organization=self.org,
        )
        self.ws = WSNumber.objects.create(
            user=None,
            organization=self.org,
            agent=self.agent,
            number="15550003333",
            platform_id="pnid-deliver",
        )
        from api.whatsapp.conversations import get_or_create_whatsapp_conversation

        self.conv = get_or_create_whatsapp_conversation(self.ws, "5939111222333")
        self.conv.whatsapp_last_inbound_wamid = "wamid.inbound.test"
        self.conv.save(update_fields=["whatsapp_last_inbound_wamid", "updated_at"])

    @patch("api.whatsapp.actions._pick_whatsapp_reaction", return_value="👍")
    @patch("api.whatsapp.actions.send_reaction")
    @patch("api.whatsapp.actions.send_message", return_value="wamid.text.out")
    @patch(
        "api.whatsapp.outbound_media.deliver_whatsapp_attachments",
        return_value=["wamid.media.out"],
    )
    def test_deliver_whatsapp_reply_sends_media_then_text(
        self, mock_deliver_media, mock_send_text, _mock_reaction, _mock_pick
    ):
        from api.whatsapp.actions import deliver_whatsapp_reply

        user_msg = Message.objects.create(
            conversation=self.conv,
            type="user",
            text="draw a cat",
            metadata={"whatsapp_inbound_wamid": "wamid.inbound.test"},
        )
        assistant = Message.objects.create(
            conversation=self.conv,
            type="assistant",
            text="Here is your image!",
        )

        deliver_whatsapp_reply(
            conversation=self.conv,
            assistant_message_id=assistant.id,
            inbound_wamid="wamid.inbound.test",
        )

        mock_deliver_media.assert_called_once()
        call_kwargs = mock_deliver_media.call_args.kwargs
        self.assertEqual(call_kwargs["reply_to_message_id"], "wamid.inbound.test")
        mock_send_text.assert_called_once()
        self.assertEqual(mock_send_text.call_args[0][2], "Here is your image!")
        self.assertIsNone(mock_send_text.call_args[0][3])

        assistant.refresh_from_db()
        self.assertEqual(assistant.metadata.get("whatsapp_wamid"), "wamid.text.out")
        self.assertEqual(
            assistant.metadata.get("whatsapp_media_wamids"), ["wamid.media.out"]
        )
        user_msg.refresh_from_db()
        self.assertEqual(user_msg.metadata.get("whatsapp_wamid"), "wamid.inbound.test")

    @patch("api.whatsapp.actions._pick_whatsapp_reaction", return_value="👍")
    @patch("api.whatsapp.actions.send_reaction")
    @patch("api.whatsapp.actions.send_message")
    @patch(
        "api.whatsapp.outbound_media.deliver_whatsapp_attachments",
        return_value=["wamid.media.only"],
    )
    def test_deliver_skips_text_when_body_empty(
        self, mock_deliver_media, mock_send_text, _mock_reaction, _mock_pick
    ):
        from api.whatsapp.actions import deliver_whatsapp_reply

        assistant = Message.objects.create(
            conversation=self.conv,
            type="assistant",
            text="   ",
        )
        deliver_whatsapp_reply(
            conversation=self.conv,
            assistant_message_id=assistant.id,
            inbound_wamid=None,
        )
        mock_deliver_media.assert_called_once()
        mock_send_text.assert_not_called()
        assistant.refresh_from_db()
        self.assertEqual(
            assistant.metadata.get("whatsapp_media_wamids"), ["wamid.media.only"]
        )
        self.assertNotIn("whatsapp_wamid", assistant.metadata)

    @patch("api.whatsapp.actions._pick_whatsapp_reaction", return_value="👍")
    @patch("api.whatsapp.actions.send_reaction")
    @patch("api.whatsapp.actions.send_message", return_value="wamid.text.only")
    @patch("api.whatsapp.outbound_media.deliver_whatsapp_attachments", return_value=[])
    def test_deliver_text_uses_reply_when_no_media(
        self, _mock_media, mock_send_text, _mock_reaction, _mock_pick
    ):
        from api.whatsapp.actions import deliver_whatsapp_reply

        Message.objects.create(
            conversation=self.conv,
            type="user",
            text="hi",
        )
        assistant = Message.objects.create(
            conversation=self.conv,
            type="assistant",
            text="Hello back",
        )
        deliver_whatsapp_reply(
            conversation=self.conv,
            assistant_message_id=assistant.id,
            inbound_wamid="wamid.inbound.test",
        )
        mock_send_text.assert_called_once()
        self.assertEqual(mock_send_text.call_args[0][3], "wamid.inbound.test")

    @patch("api.whatsapp.actions._pick_whatsapp_reaction", return_value="👍")
    @patch("api.whatsapp.actions.send_reaction")
    @patch("api.whatsapp.actions.send_message", return_value="wamid.text.clean")
    @patch("api.whatsapp.outbound_media.deliver_whatsapp_attachments", return_value=[])
    def test_deliver_strips_internal_attachment_manifest_from_text(
        self, _mock_media, mock_send_text, _mock_reaction, _mock_pick
    ):
        from api.whatsapp.actions import deliver_whatsapp_reply

        Message.objects.create(
            conversation=self.conv,
            type="user",
            text="months in japanese",
        )
        assistant = Message.objects.create(
            conversation=self.conv,
            type="assistant",
            text=(
                "Aqui tienes el audio con los meses en japones:\n\n"
                "Attachments available from this message:\n"
                "- audio/mpeg | name=speech | attachment_id=abc123\n\n"
                "Espero que sea lo que buscabas."
            ),
        )
        deliver_whatsapp_reply(
            conversation=self.conv,
            assistant_message_id=assistant.id,
            inbound_wamid="wamid.inbound.test",
        )

        mock_send_text.assert_called_once()
        self.assertEqual(
            mock_send_text.call_args[0][2],
            "Aqui tienes el audio con los meses en japones:\n\n"
            "Espero que sea lo que buscabas.",
        )

    @patch("api.whatsapp.outbound_media.requests.post")
    def test_send_attachment_prefers_https_link(self, mock_post):
        from django.core.files.base import ContentFile
        from django.test import override_settings

        from api.whatsapp.outbound_media import send_attachment_to_whatsapp

        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"messages": [{"id": "wamid.link.send"}]},
        )
        att = MessageAttachment(
            conversation=self.conv,
            kind="file",
            content_type="image/png",
        )
        att.file = ContentFile(b"\x89PNG\r\n\x1a\n", name="out.png")
        with override_settings(API_BASE_URL="https://api.example.com", MEDIA_URL="/media/"):
            wamid = send_attachment_to_whatsapp(
                "pnid-deliver",
                "5939111222333",
                att,
            )
        self.assertEqual(wamid, "wamid.link.send")
        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        self.assertEqual(payload["type"], "image")
        self.assertIn("link", payload["image"])

    def test_collect_includes_text_referenced_unlinked_attachment(self):
        from django.core.files.base import ContentFile

        from api.whatsapp.outbound_media import collect_assistant_file_attachments

        prior = MessageAttachment.objects.create(
            conversation=self.conv,
            message=None,
            kind="file",
            content_type=(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
        )
        prior.file.save("boletin.docx", ContentFile(b"PK\x03\x04docx"), save=True)

        assistant = Message.objects.create(
            conversation=self.conv,
            type="assistant",
            text=(
                f"Aqui tienes el boletin:\n\n"
                f"[Descargar boletin Word](attachment:{prior.id})"
            ),
        )
        collected = collect_assistant_file_attachments(assistant)
        self.assertEqual([str(a.id) for a in collected], [str(prior.id)])

    @patch("api.whatsapp.actions._pick_whatsapp_reaction", return_value="👍")
    @patch("api.whatsapp.actions.send_reaction")
    @patch("api.whatsapp.actions.send_message", return_value="wamid.text.att")
    @patch(
        "api.whatsapp.outbound_media.send_attachment_to_whatsapp",
        return_value="wamid.media.att",
    )
    def test_deliver_sends_text_referenced_attachment_and_strips_link(
        self, mock_send_att, mock_send_text, _mock_reaction, _mock_pick
    ):
        from django.core.files.base import ContentFile

        from api.whatsapp.actions import deliver_whatsapp_reply

        prior = MessageAttachment.objects.create(
            conversation=self.conv,
            message=None,
            kind="file",
            content_type=(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
        )
        prior.file.save("boletin.docx", ContentFile(b"PK\x03\x04docx"), save=True)

        Message.objects.create(
            conversation=self.conv,
            type="user",
            text="enviamelo",
        )
        assistant = Message.objects.create(
            conversation=self.conv,
            type="assistant",
            text=(
                f"Claro. Aqui tienes el boletin semanal:\n\n"
                f"[Descargar boletin Word](attachment:{prior.id})"
            ),
        )

        deliver_whatsapp_reply(
            conversation=self.conv,
            assistant_message_id=assistant.id,
            inbound_wamid="wamid.inbound.test",
        )

        mock_send_att.assert_called_once()
        self.assertEqual(mock_send_att.call_args[0][2].id, prior.id)
        mock_send_text.assert_called_once()
        body = mock_send_text.call_args[0][2]
        self.assertIn("Descargar boletin Word", body)
        self.assertNotIn("attachment:", body)
        self.assertNotIn(str(prior.id), body)
        assistant.refresh_from_db()
        self.assertEqual(assistant.text.count("attachment:"), 1)
        self.assertEqual(
            assistant.metadata.get("whatsapp_media_wamids"), ["wamid.media.att"]
        )

    @patch("api.whatsapp.actions._pick_whatsapp_reaction", return_value="👍")
    @patch("api.whatsapp.actions.send_reaction")
    @patch("api.whatsapp.actions.send_message", return_value="wamid.text.img")
    @patch(
        "api.whatsapp.outbound_media.send_attachment_to_whatsapp",
        return_value="wamid.media.img",
    )
    def test_deliver_strips_image_attachment_markdown(
        self, mock_send_att, mock_send_text, _mock_reaction, _mock_pick
    ):
        from django.core.files.base import ContentFile

        from api.whatsapp.actions import deliver_whatsapp_reply

        image = MessageAttachment.objects.create(
            conversation=self.conv,
            message=None,
            kind="file",
            content_type="image/png",
        )
        image.file.save("chart.png", ContentFile(b"\x89PNG\r\n\x1a\n"), save=True)

        assistant = Message.objects.create(
            conversation=self.conv,
            type="assistant",
            text=f"Aqui el grafico:\n\n![Grafico](attachment:{image.id})\n\nListo.",
        )

        deliver_whatsapp_reply(
            conversation=self.conv,
            assistant_message_id=assistant.id,
            inbound_wamid=None,
        )

        mock_send_att.assert_called_once()
        self.assertEqual(mock_send_att.call_args[0][2].id, image.id)
        body = mock_send_text.call_args[0][2]
        self.assertEqual(body, "Aqui el grafico:\n\nListo.")
        self.assertNotIn("attachment:", body)
        self.assertNotIn("Grafico", body)


class WhatsappNumberAccessScopeTests(TestCase):
    def setUp(self):
        from django.utils import timezone

        from api.ai_layers.models import LanguageModel
        from api.authenticate.models import Role, RoleAssignment, UserProfile
        from api.consumption.models import Currency
        from api.providers.models import AIProvider

        Currency.objects.get_or_create(
            name="Compute Unit", defaults={"one_usd_is": 1000}
        )
        provider = AIProvider.objects.create(name="OpenAI-wa-access")
        LanguageModel.objects.create(
            provider=provider, slug="gpt-wa-access", name="GPT WA Access"
        )
        self.owner = User.objects.create_user(username="wa_access_owner", password="x")
        self.org = Organization.objects.create(name="WA Access Org", owner=self.owner)
        self.agent = Agent.objects.create(
            name="WA Access Agent", salute="hi", organization=self.org
        )
        self.ws = WSNumber.objects.create(
            user=None,
            organization=self.org,
            agent=self.agent,
            number="15551110000",
            platform_id="pnid-access",
            access_mode=WSNumber.ACCESS_MODE_PUBLIC,
        )

        self.member = User.objects.create_user(
            username="wa_access_member", email="member@example.com", password="x"
        )
        member_profile = UserProfile.objects.get(user=self.member)
        member_profile.organization = self.org
        member_profile.is_active = True
        member_profile.phone_numbers = [
            {"country_code": "1", "number": "5552223333", "is_default": True}
        ]
        member_profile.save()
        self.member_phone = "15552223333"

        self.outsider = User.objects.create_user(
            username="wa_access_outsider", email="out@example.com", password="x"
        )
        outsider_profile = UserProfile.objects.get(user=self.outsider)
        outsider_profile.phone_numbers = [
            {"country_code": "1", "number": "5559998888", "is_default": True}
        ]
        outsider_profile.save()
        self.outsider_phone = "15559998888"

        self.role = Role.objects.create(organization=self.org, name="Access Role")
        self.other_role = Role.objects.create(organization=self.org, name="Other Role")
        RoleAssignment.objects.create(
            user=self.member,
            organization=self.org,
            role=self.role,
            from_date=timezone.now().date(),
        )

        self.client = APIClient()
        self.login_token, _ = Token.get_or_create(user=self.owner, token_type="login")

    def _auth_headers(self):
        return {"HTTP_AUTHORIZATION": f"Token {self.login_token.key}"}

    def _text_webhook(self, phone: str, wamid: str = "wamid.access"):
        return {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "pnid-access"},
                                "messages": [
                                    {
                                        "from": phone,
                                        "id": wamid,
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

    @patch("api.whatsapp.actions.mark_message_as_read")
    @patch("api.whatsapp.tasks.whatsapp_flush_inbound_agent_task.apply_async")
    def test_public_unknown_phone_creates_conversation(
        self, mock_apply_async, _mock_read
    ):
        from api.whatsapp.actions import handle_message_received

        message = self._text_webhook("15550001111")["entry"][0]["changes"][0]["value"][
            "messages"
        ][0]
        handle_message_received(self._text_webhook("15550001111"), message)

        self.assertTrue(
            Conversation.objects.filter(
                ws_number=self.ws,
                whatsapp_user_number="15550001111",
                status="active",
            ).exists()
        )
        mock_apply_async.assert_called_once()

    @patch("api.whatsapp.actions.send_message", return_value="wamid.reject")
    @patch("api.whatsapp.actions.mark_message_as_read")
    @patch("api.whatsapp.tasks.whatsapp_flush_inbound_agent_task.apply_async")
    def test_organization_allows_member_and_autolinks(
        self, mock_apply_async, _mock_read, mock_send
    ):
        from api.whatsapp.access import WHATSAPP_RESTRICTED_ACCESS_REPLY
        from api.whatsapp.actions import handle_message_received

        self.ws.access_mode = WSNumber.ACCESS_MODE_ORGANIZATION
        self.ws.save(update_fields=["access_mode", "updated_at"])

        webhook = self._text_webhook(self.member_phone, "wamid.member")
        message = webhook["entry"][0]["changes"][0]["value"]["messages"][0]
        handle_message_received(webhook, message)

        contact = WSContact.objects.get(ws_number=self.ws, number=self.member_phone)
        self.assertEqual(contact.user_id, self.member.id)
        self.assertTrue(
            Conversation.objects.filter(
                ws_number=self.ws,
                whatsapp_user_number=self.member_phone,
                status="active",
            ).exists()
        )
        mock_apply_async.assert_called_once()
        mock_send.assert_not_called()

        mock_apply_async.reset_mock()
        webhook_out = self._text_webhook(self.outsider_phone, "wamid.out")
        message_out = webhook_out["entry"][0]["changes"][0]["value"]["messages"][0]
        handle_message_received(webhook_out, message_out)

        self.assertFalse(
            Conversation.objects.filter(
                ws_number=self.ws,
                whatsapp_user_number=self.outsider_phone,
            ).exists()
        )
        mock_apply_async.assert_not_called()
        mock_send.assert_called_once()
        self.assertEqual(
            mock_send.call_args[0][2], WHATSAPP_RESTRICTED_ACCESS_REPLY
        )

    @patch("api.whatsapp.actions.send_message", return_value="wamid.reject")
    @patch("api.whatsapp.actions.mark_message_as_read")
    @patch("api.whatsapp.tasks.whatsapp_flush_inbound_agent_task.apply_async")
    def test_roles_only_allows_assignee(
        self, mock_apply_async, _mock_read, mock_send
    ):
        from api.authenticate.models import UserProfile
        from api.whatsapp.actions import handle_message_received

        other_member = User.objects.create_user(
            username="wa_access_other", email="other@example.com", password="x"
        )
        other_profile = UserProfile.objects.get(user=other_member)
        other_profile.organization = self.org
        other_profile.is_active = True
        other_profile.phone_numbers = [
            {"country_code": "1", "number": "5554445555", "is_default": True}
        ]
        other_profile.save()
        other_phone = "15554445555"

        self.ws.access_mode = WSNumber.ACCESS_MODE_ROLES
        self.ws.save(update_fields=["access_mode", "updated_at"])
        self.ws.allowed_roles.set([self.role])

        webhook = self._text_webhook(self.member_phone, "wamid.role-ok")
        handle_message_received(
            webhook, webhook["entry"][0]["changes"][0]["value"]["messages"][0]
        )
        mock_apply_async.assert_called_once()

        mock_apply_async.reset_mock()
        webhook_other = self._text_webhook(other_phone, "wamid.role-deny")
        handle_message_received(
            webhook_other,
            webhook_other["entry"][0]["changes"][0]["value"]["messages"][0],
        )
        mock_apply_async.assert_not_called()
        mock_send.assert_called_once()

    @patch("api.whatsapp.actions.send_message", return_value="wamid.reject")
    @patch("api.whatsapp.actions.mark_message_as_read")
    @patch("api.whatsapp.tasks.whatsapp_flush_inbound_agent_task.apply_async")
    def test_roles_always_allows_organization_owner(
        self, mock_apply_async, _mock_read, mock_send
    ):
        from api.authenticate.models import UserProfile
        from api.whatsapp.actions import handle_message_received

        owner_profile = UserProfile.objects.get(user=self.owner)
        owner_profile.organization = self.org
        owner_profile.is_active = True
        owner_profile.phone_numbers = [
            {"country_code": "1", "number": "5557776666", "is_default": True}
        ]
        owner_profile.save()
        owner_phone = "15557776666"

        self.ws.access_mode = WSNumber.ACCESS_MODE_ROLES
        self.ws.save(update_fields=["access_mode", "updated_at"])
        self.ws.allowed_roles.set([self.role])

        webhook = self._text_webhook(owner_phone, "wamid.owner-role")
        handle_message_received(
            webhook, webhook["entry"][0]["changes"][0]["value"]["messages"][0]
        )

        mock_apply_async.assert_called_once()
        mock_send.assert_not_called()
        contact = WSContact.objects.get(ws_number=self.ws, number=owner_phone)
        self.assertEqual(contact.user_id, self.owner.id)

    @patch("api.whatsapp.actions.send_message", return_value="wamid.reject")
    @patch("api.whatsapp.actions.mark_message_as_read")
    @patch("api.whatsapp.tasks.whatsapp_flush_inbound_agent_task.apply_async")
    def test_user_mode_only_allows_access_user(
        self, mock_apply_async, _mock_read, mock_send
    ):
        from api.whatsapp.actions import handle_message_received

        self.ws.access_mode = WSNumber.ACCESS_MODE_USER
        self.ws.access_user = self.member
        self.ws.save(update_fields=["access_mode", "access_user", "updated_at"])

        webhook = self._text_webhook(self.member_phone, "wamid.user-ok")
        handle_message_received(
            webhook, webhook["entry"][0]["changes"][0]["value"]["messages"][0]
        )
        mock_apply_async.assert_called_once()
        contact = WSContact.objects.get(ws_number=self.ws, number=self.member_phone)
        self.assertEqual(contact.user_id, self.member.id)

        mock_apply_async.reset_mock()
        webhook_out = self._text_webhook(self.outsider_phone, "wamid.user-deny")
        handle_message_received(
            webhook_out,
            webhook_out["entry"][0]["changes"][0]["value"]["messages"][0],
        )
        mock_apply_async.assert_not_called()
        mock_send.assert_called_once()

    @patch("api.whatsapp.actions.send_message", return_value="wamid.reject")
    @patch("api.whatsapp.actions.mark_message_as_read")
    @patch("api.whatsapp.tasks.whatsapp_flush_inbound_agent_task.apply_async")
    def test_restricted_without_org_denies(
        self, mock_apply_async, _mock_read, mock_send
    ):
        from api.whatsapp.actions import handle_message_received

        # Personal line whose owner has no organization → resolved org is None.
        solo = User.objects.create_user(username="wa_access_solo", password="x")
        personal = WSNumber.objects.create(
            user=solo,
            organization=None,
            agent=self.agent,
            number="15551112222",
            platform_id="pnid-access-personal",
            access_mode=WSNumber.ACCESS_MODE_ORGANIZATION,
        )
        webhook = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {
                                    "phone_number_id": "pnid-access-personal"
                                },
                                "messages": [
                                    {
                                        "from": self.member_phone,
                                        "id": "wamid.no-org",
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
        handle_message_received(
            webhook, webhook["entry"][0]["changes"][0]["value"]["messages"][0]
        )
        self.assertFalse(
            Conversation.objects.filter(ws_number=personal).exists()
        )
        mock_apply_async.assert_not_called()
        mock_send.assert_called_once()

    @patch(
        "api.whatsapp.views.FeatureFlagService.is_feature_enabled",
        return_value=(True, "on"),
    )
    def test_put_access_mode_organization(self, _mock_ff):
        response = self.client.put(
            f"/v1/whatsapp/numbers/{self.ws.number}",
            data=json.dumps({"access_mode": "organization"}),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["access_mode"], "organization")
        self.assertIsNone(body["access_user_id"])
        self.assertEqual(body["allowed_roles"], [])
        self.ws.refresh_from_db()
        self.assertEqual(self.ws.access_mode, WSNumber.ACCESS_MODE_ORGANIZATION)

    @patch(
        "api.whatsapp.views.FeatureFlagService.is_feature_enabled",
        return_value=(True, "on"),
    )
    def test_put_access_mode_roles_and_user_validation(self, _mock_ff):
        bad_roles = self.client.put(
            f"/v1/whatsapp/numbers/{self.ws.number}",
            data=json.dumps({"access_mode": "roles", "allowed_role_ids": []}),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(bad_roles.status_code, 400)

        ok_roles = self.client.put(
            f"/v1/whatsapp/numbers/{self.ws.number}",
            data=json.dumps(
                {
                    "access_mode": "roles",
                    "allowed_role_ids": [str(self.role.id)],
                }
            ),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(ok_roles.status_code, 200)
        self.assertEqual(ok_roles.json()["access_mode"], "roles")
        self.assertEqual(
            [r["id"] for r in ok_roles.json()["allowed_roles"]],
            [str(self.role.id)],
        )

        bad_user = self.client.put(
            f"/v1/whatsapp/numbers/{self.ws.number}",
            data=json.dumps(
                {"access_mode": "user", "access_user_id": self.outsider.id}
            ),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(bad_user.status_code, 400)

        ok_user = self.client.put(
            f"/v1/whatsapp/numbers/{self.ws.number}",
            data=json.dumps(
                {"access_mode": "user", "access_user_id": self.member.id}
            ),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(ok_user.status_code, 200)
        self.assertEqual(ok_user.json()["access_mode"], "user")
        self.assertEqual(ok_user.json()["access_user_id"], self.member.id)
        self.assertEqual(ok_user.json()["allowed_roles"], [])

    @patch(
        "api.whatsapp.views.resolved_organization_for_ws_number",
        return_value=None,
    )
    @patch(
        "api.whatsapp.views.FeatureFlagService.is_feature_enabled",
        return_value=(True, "on"),
    )
    def test_put_restricted_requires_organization(self, _mock_ff, _mock_org):
        response = self.client.put(
            f"/v1/whatsapp/numbers/{self.ws.number}",
            data=json.dumps({"access_mode": "organization"}),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Organization is required", response.json()["error"])

    @patch("api.whatsapp.actions.send_message", return_value="wamid.reject")
    @patch("api.whatsapp.actions.mark_message_as_read")
    @patch("api.whatsapp.tasks.whatsapp_flush_inbound_agent_task.apply_async")
    def test_mexico_e164_profile_matches_meta_inbound(
        self, mock_apply_async, _mock_read, mock_send
    ):
        """
        Member saved ITU E.164 (+52 + 10 digits); Meta webhook sends 521…
        """
        from api.authenticate.models import UserProfile
        from api.whatsapp.actions import handle_message_received

        mx_member = User.objects.create_user(
            username="wa_mx_member", email="mx@example.com", password="x"
        )
        profile = UserProfile.objects.get(user=mx_member)
        profile.organization = self.org
        profile.is_active = True
        # Legacy / user-entered E.164 without Meta's "1" (bypass setter transform
        # is unnecessary: setter also normalizes — use raw column to simulate
        # pre-normalization rows still in DB).
        profile._phone_numbers = [
            {"country_code": "52", "number": "5512345678", "is_default": True}
        ]
        profile.save()

        self.ws.access_mode = WSNumber.ACCESS_MODE_ORGANIZATION
        self.ws.save(update_fields=["access_mode", "updated_at"])

        meta_from = "5215512345678"
        webhook = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "pnid-access"},
                                "messages": [
                                    {
                                        "from": meta_from,
                                        "id": "wamid.mx-meta",
                                        "type": "text",
                                        "text": {"body": "Hola"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }
        handle_message_received(
            webhook, webhook["entry"][0]["changes"][0]["value"]["messages"][0]
        )

        mock_apply_async.assert_called_once()
        mock_send.assert_not_called()
        contact = WSContact.objects.get(ws_number=self.ws, number=meta_from)
        self.assertEqual(contact.user_id, mx_member.id)
