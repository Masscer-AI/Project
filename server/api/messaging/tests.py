from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from api.ai_layers.models import Agent, LanguageModel
from api.authenticate.models import Organization
from api.messaging.models import ChatWidget, Conversation, WidgetVisitorSession
from api.messaging.serializers import ChatWidgetSerializer
from api.providers.models import AIProvider


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
    def test_widget_agent_task_uses_only_enabled_capabilities_plus_base_tools(
        self, delay_mock
    ):
        delay_mock.return_value = Mock(id="task-123")
        widget = ChatWidget.objects.create(
            name="Widget D",
            enabled=True,
            created_by=self.user,
            agent=self.agent,
            capabilities=[
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
