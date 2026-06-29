import base64
import json
import tempfile
from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from api.ai_layers.models import Agent, LanguageModel
from api.authenticate.models import Organization, Token, UserProfile
from api.messaging.models import ChatWidget, Conversation, Message, WidgetVisitorSession
from api.messaging.serializers import ChatWidgetSerializer
from api.messaging.widget_avatar_urls import resolved_avatar_image
from api.providers.models import AIProvider

MINIMAL_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class ChatWidgetCapabilitiesTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="widget-owner",
            email="owner@example.com",
            password="pass-123456",
        )
        provider = AIProvider.objects.create(name="OpenAI")
        llm = LanguageModel.objects.create(
            provider=provider,
            slug="gpt-4o-mini",
            name="GPT 4o mini",
        )
        self.agent = Agent.objects.create(
            name="Widget Agent",
            salute="hello",
            act_as="helpful assistant",
            user=self.user,
            llm=llm,
            model_slug=llm.slug,
            model_provider="openai",
        )

    def test_serializer_rejects_malformed_capabilities(self):
        serializer = ChatWidgetSerializer(data={"name": "Widget A", "capabilities": {"bad": True}})
        self.assertFalse(serializer.is_valid())
        self.assertIn("capabilities", serializer.errors)

    def test_serializer_rejects_unknown_capability_name(self):
        serializer = ChatWidgetSerializer(
            data={
                "name": "Widget B",
                "capabilities": [
                    {"name": "unknown_tool", "type": "internal_tool", "enabled": True}
                ],
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("capabilities", serializer.errors)

    def test_serializer_accepts_data_url_avatar_image(self):
        serializer = ChatWidgetSerializer(
            data={
                "name": "Widget Avatar Data URL",
                "avatar_image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_serializer_rejects_non_http_and_non_data_avatar_image(self):
        serializer = ChatWidgetSerializer(
            data={
                "name": "Widget Bad Avatar",
                "avatar_image": "ftp://example.com/avatar.png",
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("avatar_image", serializer.errors)

    def test_widget_config_includes_first_message_and_capabilities(self):
        widget = ChatWidget.objects.create(
            name="Widget C",
            enabled=True,
            avatar_image="https://cdn.example.com/widget-avatar.png",
            created_by=self.user,
            agent=self.agent,
            first_message="Welcome to the widget",
            capabilities=[
                {"name": "explore_web", "type": "internal_tool", "enabled": True},
            ],
        )

        response = self.client.get(f"/v1/messaging/widgets/{widget.token}/config/")
        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertIn("first_message", body)
        self.assertIn("capabilities", body)
        self.assertIn("avatar_image", body)
        self.assertEqual(body["first_message"], "Welcome to the widget")
        self.assertEqual(body["avatar_image"], "https://cdn.example.com/widget-avatar.png")
        self.assertEqual(len(body["capabilities"]), 1)

    @patch("api.messaging.tasks.widget_conversation_agent_task.delay")
    def test_widget_agent_task_uses_only_enabled_capabilities(
        self, delay_mock
    ):
        delay_mock.return_value = Mock(id="task-123")
        widget = ChatWidget.objects.create(
            name="Widget D",
            enabled=True,
            created_by=self.user,
            agent=self.agent,
            capabilities=[
                {"name": "read_attachment", "type": "internal_tool", "enabled": True},
                {"name": "list_attachments", "type": "internal_tool", "enabled": True},
                {"name": "explore_web", "type": "internal_tool", "enabled": True},
                {"name": "rag_query", "type": "internal_tool", "enabled": False},
                {"name": "create_image", "type": "internal_tool", "enabled": True},
            ],
        )

        session_response = self.client.get(f"/v1/messaging/widgets/{widget.token}/session/")
        self.assertEqual(session_response.status_code, 200)
        widget_session_token = session_response.json()["token"]

        auth_header = {"HTTP_AUTHORIZATION": f"WidgetSession {widget_session_token}"}
        conversation_response = self.client.post(
            f"/v1/messaging/widgets/{widget.token}/conversation/",
            data={},
            format="json",
            **auth_header,
        )
        self.assertIn(conversation_response.status_code, [200, 201])
        conversation_id = conversation_response.json()["id"]

        task_response = self.client.post(
            f"/v1/messaging/widgets/{widget.token}/agent-task/",
            data={
                "conversation_id": conversation_id,
                "user_inputs": [{"type": "input_text", "text": "hello"}],
            },
            format="json",
            **auth_header,
        )

        self.assertEqual(task_response.status_code, 202)
        self.assertTrue(delay_mock.called)

        kwargs = delay_mock.call_args.kwargs
        tool_names = kwargs["tool_names"]
        self.assertIn("read_attachment", tool_names)
        self.assertIn("list_attachments", tool_names)
        self.assertIn("explore_web", tool_names)
        self.assertIn("create_image", tool_names)
        self.assertNotIn("rag_query", tool_names)

    @patch("api.ai_layers.tools.create_image.OpenAI")
    @patch("api.authenticate.services.FeatureFlagService.is_feature_enabled")
    def test_create_image_widget_conversation_does_not_require_image_tools_flag(
        self, is_feature_enabled_mock, openai_cls_mock
    ):
        """Widget tools are gated by ChatWidget.capabilities; visitors are not users for FF checks."""
        from api.ai_layers.tools.create_image import _create_image_impl

        org = Organization.objects.create(name="Widget Org", owner=self.user)
        widget = ChatWidget.objects.create(
            name="Widget Image",
            enabled=True,
            created_by=self.user,
            agent=self.agent,
            capabilities=[
                {"name": "create_image", "type": "internal_tool", "enabled": True},
            ],
        )
        session = WidgetVisitorSession.objects.create(
            widget=widget,
            visitor_id="visitor-create-image",
            expires_at=timezone.now() + timedelta(days=1),
        )
        conversation = Conversation.objects.create(
            user=None,
            organization=org,
            chat_widget=widget,
            widget_visitor_session=session,
        )

        is_feature_enabled_mock.return_value = (False, "off")

        client_inst = Mock()
        openai_cls_mock.return_value = client_inst
        img_obj = Mock(b64_json="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
        client_inst.images.generate.return_value = Mock(data=[img_obj])

        result = _create_image_impl(
            prompt="test png",
            model="gpt-image-1.5",
            aspect_ratio="square",
            conversation_id=str(conversation.id),
            user_id=None,
            agent_slug=self.agent.slug,
        )

        is_feature_enabled_mock.assert_not_called()
        self.assertEqual(result.model, "gpt-image-1.5")

    def test_widget_agent_task_rejects_input_attachment_when_visitor_uploads_disabled(
        self,
    ):
        widget = ChatWidget.objects.create(
            name="Widget No Visitor Files",
            enabled=True,
            created_by=self.user,
            agent=self.agent,
            style={},
            capabilities=[
                {"name": "read_attachment", "type": "internal_tool", "enabled": True},
            ],
        )

        session_response = self.client.get(f"/v1/messaging/widgets/{widget.token}/session/")
        self.assertEqual(session_response.status_code, 200)
        widget_session_token = session_response.json()["token"]

        auth_header = {"HTTP_AUTHORIZATION": f"WidgetSession {widget_session_token}"}
        conversation_response = self.client.post(
            f"/v1/messaging/widgets/{widget.token}/conversation/",
            data={},
            format="json",
            **auth_header,
        )
        self.assertIn(conversation_response.status_code, [200, 201])
        conversation_id = conversation_response.json()["id"]

        task_response = self.client.post(
            f"/v1/messaging/widgets/{widget.token}/agent-task/",
            data={
                "conversation_id": conversation_id,
                "user_inputs": [
                    {"type": "input_text", "text": "hello"},
                    {"type": "input_attachment", "attachment_id": "550e8400-e29b-41d4-a716-446655440000"},
                ],
            },
            format="json",
            **auth_header,
        )

        self.assertEqual(task_response.status_code, 403)


class MessagePostSaveBillingTests(TestCase):
    @patch("api.messaging.signals.async_register_llm_interaction")
    def test_anonymous_conversation_bills_org_owner(self, delay_mock):
        owner = User.objects.create_user(username="org-owner-bill", password="x")
        org = Organization.objects.create(name="Bill Org", owner=owner)
        conversation = Conversation.objects.create(user=None, organization=org)

        Message.objects.create(
            conversation=conversation,
            type="assistant",
            versions=[
                {
                    "usage": {
                        "model_slug": "gpt-4o-mini",
                        "prompt_tokens": 10,
                        "completion_tokens": 20,
                    }
                }
            ],
        )

        delay_mock.delay.assert_called_once_with(
            owner.id,
            10,
            20,
            "gpt-4o-mini",
            org.id,
        )

    @patch("api.messaging.signals.async_register_llm_interaction")
    def test_conversation_without_user_or_org_skips_billing(self, delay_mock):
        conversation = Conversation.objects.create(user=None, organization=None)
        Message.objects.create(
            conversation=conversation,
            type="assistant",
            versions=[
                {
                    "usage": {
                        "model_slug": "gpt-4o-mini",
                        "prompt_tokens": 5,
                        "completion_tokens": 7,
                    }
                }
            ],
        )

        delay_mock.delay.assert_not_called()


class ConversationTakeoverTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.operator = User.objects.create_user(
            username="operator",
            email="op@example.com",
            password="pass-123456",
        )
        self.other = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="pass-123456",
        )
        self.org = Organization.objects.create(name="Takeover Org", owner=self.operator)
        UserProfile.objects.create(user=self.other, organization=self.org)
        provider = AIProvider.objects.create(name="OpenAI")
        llm = LanguageModel.objects.create(
            provider=provider,
            slug="gpt-4o-mini",
            name="GPT 4o mini",
        )
        self.agent = Agent.objects.create(
            name="WA Agent",
            salute="hi",
            act_as="helpful",
            user=self.operator,
            llm=llm,
            model_slug=llm.slug,
            model_provider="openai",
        )
        from api.whatsapp.models import WSNumber

        self.ws_number = WSNumber.objects.create(
            organization=self.org,
            agent=self.agent,
            number="5215551234567",
            platform_id="123456",
        )
        self.conversation = Conversation.objects.create(
            user=None,
            organization=self.org,
            ws_number=self.ws_number,
            whatsapp_user_number="5215559999999",
        )
        self.client.force_authenticate(user=self.operator)

    @patch("api.messaging.takeover.notify_user")
    @patch("api.messaging.takeover.send_takeover_announcement")
    @patch("api.messaging.views.user_can_replace_agent", return_value=True)
    def test_start_takeover_creates_active_row(
        self, _flag_mock, announce_mock, notify_mock
    ):
        announce_mock.return_value = None
        response = self.client.post(
            f"/v1/messaging/conversations/{self.conversation.id}/takeover/"
        )
        self.assertEqual(response.status_code, 200)
        from api.messaging.models import ConversationTakeover

        takeover = ConversationTakeover.objects.get(conversation=self.conversation)
        self.assertEqual(takeover.status, ConversationTakeover.Status.ACTIVE)
        self.assertEqual(takeover.user_id, self.operator.id)
        data = response.json()
        self.assertIsNotNone(data.get("active_takeover"))

    @patch("api.messaging.takeover.notify_user")
    @patch("api.messaging.takeover.send_takeover_announcement")
    @patch("api.messaging.views.user_can_replace_agent", return_value=True)
    def test_second_operator_gets_conflict(
        self, _flag_mock, announce_mock, notify_mock
    ):
        announce_mock.return_value = None
        from api.messaging.takeover import start_takeover

        start_takeover(self.conversation, self.operator)
        self.client.force_authenticate(user=self.other)
        response = self.client.post(
            f"/v1/messaging/conversations/{self.conversation.id}/takeover/"
        )
        self.assertEqual(response.status_code, 409)

    @patch("api.messaging.takeover.notify_user")
    @patch("api.messaging.takeover.send_takeover_announcement")
    @patch("api.messaging.views.user_can_replace_agent", return_value=True)
    def test_release_sets_inactive_and_metadata_reason(
        self, _flag_mock, announce_mock, notify_mock
    ):
        announce_mock.return_value = None
        from api.messaging.takeover import start_takeover
        from api.messaging.models import ConversationTakeover

        takeover = start_takeover(self.conversation, self.operator)
        response = self.client.delete(
            f"/v1/messaging/conversations/{self.conversation.id}/takeover/"
        )
        self.assertEqual(response.status_code, 200)
        takeover.refresh_from_db()
        self.assertEqual(takeover.status, ConversationTakeover.Status.INACTIVE)
        self.assertIsNotNone(takeover.ended_at)
        self.assertEqual(takeover.metadata.get("ended_reason"), "manual_release")

    @patch("api.messaging.takeover.emit_message_created")
    @patch("api.messaging.takeover.notify_widget_human_reply")
    @patch("api.messaging.views.user_can_replace_agent", return_value=True)
    def test_human_message_whatsapp_via_takeover(
        self, _flag_mock, widget_notify_mock, emit_mock
    ):
        from api.messaging.takeover import start_takeover

        takeover = start_takeover(self.conversation, self.operator)
        with patch.object(
            type(self.ws_number), "send_message", return_value="wamid-1"
        ) as send_mock:
            with patch(
                "api.messaging.takeover.send_takeover_announcement",
                return_value=None,
            ):
                response = self.client.post(
                    f"/v1/messaging/conversations/{self.conversation.id}/human-message/",
                    data={"message": "Hola desde humano"},
                    format="json",
                )
        self.assertEqual(response.status_code, 201)
        send_mock.assert_called_once()
        msg = Message.objects.filter(
            conversation=self.conversation, type="assistant"
        ).order_by("-id").first()
        self.assertEqual(msg.text, "Hola desde humano")
        self.assertTrue(msg.metadata.get("human_takeover"))

    @patch("api.messaging.takeover.notify_user")
    @patch("api.ai_layers.tasks.conversation_agent_task")
    def test_whatsapp_inbound_skips_agent_when_takeover_active(
        self, agent_task_mock, notify_mock
    ):
        from api.messaging.models import ConversationTakeover
        from api.messaging.takeover import start_takeover
        from api.whatsapp.inbound import enqueue_whatsapp_inbound_agent

        with patch(
            "api.messaging.takeover.send_takeover_announcement",
            return_value=None,
        ):
            start_takeover(self.conversation, self.operator)

        enqueue_whatsapp_inbound_agent(
            conversation=self.conversation,
            ws_number=self.ws_number,
            whatsapp_user_number="5215559999999",
            inbound_wamid="wamid-in-1",
            user_inputs=[{"type": "input_text", "text": "Necesito ayuda"}],
        )

        agent_task_mock.delay.assert_not_called()
        user_msg = Message.objects.filter(
            conversation=self.conversation,
            type="user",
            metadata__whatsapp_inbound_wamid="wamid-in-1",
        ).first()
        self.assertIsNotNone(user_msg)
        self.assertEqual(user_msg.text, "Necesito ayuda")
        self.assertTrue(
            ConversationTakeover.objects.filter(
                conversation=self.conversation,
                status=ConversationTakeover.Status.ACTIVE,
            ).exists()
        )


@override_settings(API_BASE_URL="https://api.example.com")
class ChatWidgetAvatarUploadTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.mkdtemp()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_dir)
        self.settings_override.enable()

        self.client = APIClient()
        self.user = User.objects.create_user(
            username="widget-avatar-owner",
            email="avatar-owner@example.com",
            password="pass-123456",
        )
        self.login_token, _ = Token.get_or_create(user=self.user, token_type="login")
        self.auth = {"HTTP_AUTHORIZATION": f"Token {self.login_token.key}"}

        provider = AIProvider.objects.create(name="OpenAI Avatar")
        llm = LanguageModel.objects.create(
            provider=provider,
            slug="gpt-4o-mini-avatar",
            name="GPT 4o mini avatar",
        )
        self.agent = Agent.objects.create(
            name="Avatar Agent",
            salute="hello",
            act_as="helpful assistant",
            user=self.user,
            llm=llm,
            model_slug=llm.slug,
            model_provider="openai",
        )
        self.widget = ChatWidget.objects.create(
            name="Avatar Widget",
            enabled=True,
            created_by=self.user,
            agent=self.agent,
        )

    def tearDown(self):
        self.settings_override.disable()

    def _upload_avatar(self, widget_id=None, filename="avatar.png"):
        widget_id = widget_id or self.widget.id
        uploaded = SimpleUploadedFile(
            filename,
            MINIMAL_PNG_BYTES,
            content_type="image/png",
        )
        return self.client.post(
            f"/v1/messaging/widgets/{widget_id}/avatar/",
            {"avatar": uploaded},
            format="multipart",
            **self.auth,
        )

    @patch(
        "api.authenticate.services.FeatureFlagService.is_feature_enabled",
        return_value=(True, "on"),
    )
    def test_upload_avatar_returns_absolute_url_in_widget_and_config(self, _ff_mock):
        response = self._upload_avatar()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["avatar_image"].startswith("https://api.example.com/"))

        self.widget.refresh_from_db()
        self.assertTrue(self.widget.avatar)
        self.assertEqual(self.widget.avatar_image, "")

        config_response = self.client.get(
            f"/v1/messaging/widgets/{self.widget.token}/config/"
        )
        self.assertEqual(config_response.status_code, 200)
        self.assertTrue(
            config_response.json()["avatar_image"].startswith("https://api.example.com/")
        )

    @patch(
        "api.authenticate.services.FeatureFlagService.is_feature_enabled",
        return_value=(True, "on"),
    )
    def test_upload_replaces_previous_avatar_file(self, _ff_mock):
        first = self._upload_avatar()
        self.assertEqual(first.status_code, 200)
        self.widget.refresh_from_db()
        first_path = self.widget.avatar.name

        second = self._upload_avatar(filename="avatar2.png")
        self.assertEqual(second.status_code, 200)
        self.widget.refresh_from_db()
        self.assertNotEqual(self.widget.avatar.name, first_path)

    @patch(
        "api.authenticate.services.FeatureFlagService.is_feature_enabled",
        return_value=(True, "on"),
    )
    def test_delete_avatar_clears_file_and_config(self, _ff_mock):
        self._upload_avatar()
        delete_response = self.client.delete(
            f"/v1/messaging/widgets/{self.widget.id}/avatar/",
            **self.auth,
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json().get("avatar_image"), "")

        self.widget.refresh_from_db()
        self.assertFalse(self.widget.avatar)
        self.assertEqual(self.widget.avatar_image, "")

        config_response = self.client.get(
            f"/v1/messaging/widgets/{self.widget.token}/config/"
        )
        self.assertEqual(config_response.json().get("avatar_image"), "")

    @patch(
        "api.authenticate.services.FeatureFlagService.is_feature_enabled",
        return_value=(True, "on"),
    )
    def test_put_avatar_image_url_clears_uploaded_file(self, _ff_mock):
        self._upload_avatar()
        self.widget.refresh_from_db()
        self.assertTrue(self.widget.avatar)

        external_url = "https://cdn.example.com/widget-avatar.png"
        put_response = self.client.put(
            f"/v1/messaging/widgets/{self.widget.id}/",
            data=json.dumps({"avatar_image": external_url}),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(put_response.status_code, 200)
        self.assertEqual(put_response.json().get("avatar_image"), external_url)

        self.widget.refresh_from_db()
        self.assertFalse(self.widget.avatar)
        self.assertEqual(self.widget.avatar_image, external_url)
        self.assertEqual(resolved_avatar_image(self.widget), external_url)

    @patch(
        "api.authenticate.services.FeatureFlagService.is_feature_enabled",
        return_value=(True, "on"),
    )
    def test_upload_rejects_oversized_file(self, _ff_mock):
        oversized = SimpleUploadedFile(
            "big.png",
            MINIMAL_PNG_BYTES,
            content_type="image/png",
        )
        oversized.size = 3 * 1024 * 1024
        response = self.client.post(
            f"/v1/messaging/widgets/{self.widget.id}/avatar/",
            {"avatar": oversized},
            format="multipart",
            **self.auth,
        )
        self.assertEqual(response.status_code, 400)


class MessageAttachmentXlsxUploadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u-xlsx", password="x")
        self.conversation = Conversation.objects.create(user=self.user)

    def test_create_attachments_from_data_urls_maps_xlsx_mime(self):
        from api.messaging.views import _create_attachments_from_data_urls
        from api.utils.spreadsheet_tools import build_xlsx_bytes_from_sheets

        raw = build_xlsx_bytes_from_sheets(
            [
                {
                    "name": "Sheet1",
                    "headers": ["A"],
                    "rows": [["1"]],
                }
            ]
        )
        b64 = base64.b64encode(raw).decode("ascii")
        data_url = (
            "data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,"
            + b64
        )
        request = Mock()
        request.build_absolute_uri = lambda url: f"https://example.com{url}"

        result, err = _create_attachments_from_data_urls(
            request,
            self.conversation,
            self.user,
            [{"content": data_url, "name": "sheet.xlsx"}],
        )

        self.assertIsNone(err)
        self.assertEqual(len(result), 1)
        from api.messaging.models import MessageAttachment

        att = MessageAttachment.objects.get(id=result[0]["id"])
        self.assertEqual(
            att.content_type,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertTrue(att.file.name.endswith(".xlsx"))
