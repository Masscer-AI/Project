from unittest.mock import MagicMock, patch

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from api.authenticate.models import Organization, Token
from api.ai_layers.models import Agent
from api.messaging.models import Conversation, Message, MessageAttachment
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
            {"name": "read_plugin_instructions", "type": "internal_tool", "enabled": True},
        ]
        names = tool_names_from_capabilities(caps)
        self.assertIn("rag_query", names)
        self.assertIn("read_attachment", names)
        self.assertIn("list_attachments", names)
        self.assertNotIn("not_a_real_tool", names)
        self.assertNotIn("explore_web", names)
        self.assertNotIn("read_plugin_instructions", names)

    def test_tool_names_from_capabilities_forces_required_when_disabled(self):
        caps = [
            {"name": "read_attachment", "type": "internal_tool", "enabled": False},
            {"name": "list_attachments", "type": "internal_tool", "enabled": False},
        ]
        names = tool_names_from_capabilities(caps)
        self.assertIn("read_attachment", names)
        self.assertIn("list_attachments", names)

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
        from django.core.cache import cache

        cache.clear()
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
            ws_number=self.ws, whatsapp_user_number="5490000000000"
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
        self.assertEqual(stub.text, ".")

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
            ws_number=self.ws, whatsapp_user_number="5490000000000"
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

    def test_put_capabilities_rejects_plugin_tools(self, _mock_ff):
        response = self.client.put(
            f"/v1/whatsapp/numbers/{self.ws.number}",
            data=json.dumps(
                {
                    "capabilities": [
                        {
                            "name": "read_plugin_instructions",
                            "type": "internal_tool",
                            "enabled": True,
                        }
                    ]
                }
            ),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 400)
        body = response.json()
        details_str = json.dumps(body.get("details", ""))
        self.assertIn("not available on WhatsApp", details_str)

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
        self.assertEqual(
            response.json()["capabilities"],
            [
                {"name": "rag_query", "type": "internal_tool", "enabled": True},
                {"name": "read_attachment", "type": "internal_tool", "enabled": True},
                {"name": "list_attachments", "type": "internal_tool", "enabled": True},
            ],
        )
        self.ws.refresh_from_db()
        self.assertEqual(
            self.ws.capabilities,
            [
                {"name": "rag_query", "type": "internal_tool", "enabled": True},
                {"name": "read_attachment", "type": "internal_tool", "enabled": True},
                {"name": "list_attachments", "type": "internal_tool", "enabled": True},
            ],
        )

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
            [
                {"name": "read_attachment", "type": "internal_tool", "enabled": True},
                {"name": "list_attachments", "type": "internal_tool", "enabled": True},
            ],
        )


@patch("api.authenticate.services.FeatureFlagService.is_feature_enabled")
class WhatsappEmbeddedMediaToolTests(TestCase):
    """WhatsApp lines gate create_image / create_speech via capabilities, not app feature flags."""

    def setUp(self):
        self.owner = User.objects.create_user(username="wa_media_owner", password="x")
        self.org = Organization.objects.create(name="WA Media Org", owner=self.owner)
        self.agent = Agent.objects.create(
            name="WA Media Agent",
            salute="hi",
            organization=self.org,
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
            model="gpt-image-1.5",
            aspect_ratio="square",
            conversation_id=str(conv.id),
            user_id=None,
            agent_slug=self.agent.slug,
        )

        is_feature_enabled_mock.assert_not_called()
        self.assertEqual(result.model, "gpt-image-1.5")

    @patch("api.ai_layers.tools.create_speech._generate_openai_tts_bytes", return_value=b"fake-audio")
    def test_create_speech_skips_chat_generate_speech_flag_for_whatsapp_conversation(
        self, _tts_mock, is_feature_enabled_mock
    ):
        from api.ai_layers.tools.create_speech import _create_speech_impl
        from api.whatsapp.conversations import get_or_create_whatsapp_conversation

        is_feature_enabled_mock.return_value = (False, "off")
        conv = get_or_create_whatsapp_conversation(self.ws, "5939000000002")

        result = _create_speech_impl(
            text="hello",
            voice="coral",
            instructions="",
            output_format="mp3",
            conversation_id=str(conv.id),
            user_id=None,
            agent_slug=self.agent.slug,
        )

        is_feature_enabled_mock.assert_not_called()
        self.assertEqual(result.output_format, "mp3")


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
        "api.whatsapp.actions.deliver_whatsapp_attachments",
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
        "api.whatsapp.actions.deliver_whatsapp_attachments",
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
    @patch("api.whatsapp.actions.deliver_whatsapp_attachments", return_value=[])
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
    @patch("api.whatsapp.actions.deliver_whatsapp_attachments", return_value=[])
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
            "Aqui tienes el audio con los meses en japones:\n"
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
