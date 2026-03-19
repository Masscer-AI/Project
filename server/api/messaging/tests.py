from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from api.ai_layers.models import Agent, LanguageModel
from api.messaging.models import ChatWidget
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

    def test_widget_config_includes_first_message_and_capabilities(self):
        widget = ChatWidget.objects.create(
            name="Widget C",
            enabled=True,
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
        self.assertEqual(body["first_message"], "Welcome to the widget")
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
