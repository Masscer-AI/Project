from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient


class ConversationTaggingToolsRegistryTests(SimpleTestCase):
    def test_tagging_tools_are_registered(self):
        from api.ai_layers.tools import list_available_tools

        names = list_available_tools()
        for required in (
            "query_organization_tags",
            "create_organization_tag",
            "change_conversation_tags",
            "change_conversation_summary",
            "get_tag_context",
            "query_conversation",
        ):
            self.assertIn(required, names)


class PluginRegistryTests(SimpleTestCase):
    def test_format_plugins_instruction_empty_when_none(self):
        from api.ai_layers.plugins import format_plugins_instruction

        self.assertEqual(format_plugins_instruction(None), "")
        self.assertEqual(format_plugins_instruction([]), "")

    def test_format_plugins_instruction_includes_enabled_plugin(self):
        from api.ai_layers.plugins import format_plugins_instruction

        rendered = format_plugins_instruction(["calculator"])
        self.assertIn("# Plugins enabled", rendered)
        self.assertIn("slug: calculator", rendered)
        self.assertIn("JSON Structure", rendered)

    def test_format_plugins_instruction_ignores_unknown(self):
        from api.ai_layers.plugins import format_plugins_instruction

        self.assertEqual(format_plugins_instruction(["not-a-real-plugin"]), "")


class AgentSessionExecutionLogTests(SimpleTestCase):
    def test_extract_tool_calls_pairs_function_calls_with_outputs(self):
        from api.ai_layers.serializers import extract_tool_calls_from_messages

        messages = [
            {"role": "user", "content": "hello"},
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "search_docs",
                "arguments": '{"query":"pricing"}',
            },
            {
                "type": "function_call",
                "call_id": "call_2",
                "name": "web_search",
                "arguments": {"query": "weather"},
            },
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": '{"documents":[{"id":1}]}',
            },
            {
                "type": "function_call_output",
                "call_id": "call_2",
                "output": '{"error":"network timeout"}',
            },
        ]

        tool_calls = extract_tool_calls_from_messages(messages)

        self.assertEqual(len(tool_calls), 2)
        self.assertEqual(tool_calls[0]["order"], 1)
        self.assertEqual(tool_calls[0]["iteration"], 1)
        self.assertEqual(tool_calls[0]["tool_name"], "search_docs")
        self.assertEqual(tool_calls[0]["arguments"], {"query": "pricing"})
        self.assertEqual(tool_calls[0]["result"], {"documents": [{"id": 1}]})
        self.assertEqual(tool_calls[0]["error"], None)

        self.assertEqual(tool_calls[1]["order"], 2)
        self.assertEqual(tool_calls[1]["iteration"], 1)
        self.assertEqual(tool_calls[1]["tool_name"], "web_search")
        self.assertEqual(tool_calls[1]["arguments"], {"query": "weather"})
        self.assertEqual(tool_calls[1]["error"], "network timeout")

    def test_extract_tool_calls_infers_new_iteration_for_later_batch(self):
        from api.ai_layers.serializers import extract_tool_calls_from_messages

        messages = [
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "search_docs",
                "arguments": "{}",
            },
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": '{"ok":true}',
            },
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "thinking"}],
            },
            {
                "type": "function_call",
                "call_id": "call_2",
                "name": "fetch_page",
                "arguments": "{}",
            },
            {
                "type": "function_call_output",
                "call_id": "call_2",
                "output": '{"ok":true}',
            },
        ]

        tool_calls = extract_tool_calls_from_messages(messages)

        self.assertEqual([call["iteration"] for call in tool_calls], [1, 2])


class VertexGeminiTextHelpersTests(SimpleTestCase):
    def test_messages_to_contents_maps_assistant_to_model(self):
        from google.genai import types as genai_types

        from api.utils.vertex_gemini_text import _openai_style_messages_to_contents

        contents = _openai_style_messages_to_contents(
            [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello"},
            ],
            genai_types=genai_types,
        )
        self.assertEqual(len(contents), 2)
        self.assertEqual(contents[0].role, "user")
        self.assertEqual(contents[1].role, "model")

    def test_extract_text_concatenates_parts(self):
        from types import SimpleNamespace

        from api.utils.vertex_gemini_text import _extract_text_from_response

        part = SimpleNamespace(text="ab")
        content = SimpleNamespace(parts=[part])
        cand = SimpleNamespace(content=content)
        resp = SimpleNamespace(candidates=[cand])
        self.assertEqual(_extract_text_from_response(resp), "ab")

    def test_default_model_constant(self):
        from api.utils.vertex_gemini_text import DEFAULT_VERTEX_TEXT_MODEL

        self.assertEqual(DEFAULT_VERTEX_TEXT_MODEL, "gemini-3.1-flash-lite-preview")


class AgentTaskConversationMetadataTests(TestCase):
    """related_agents metadata is written on agent-task POST (not via conversation PUT)."""

    @patch("api.ai_layers.views.conversation_agent_task.delay")
    def test_post_persists_related_agents_metadata(self, mock_delay):
        mock_delay.return_value = Mock(id="celery-task-1")
        user = User.objects.create_user(username="u1", email="u1@e.com", password="x")
        client = APIClient()
        client.force_authenticate(user=user)

        from api.ai_layers.models import Agent, LanguageModel
        from api.messaging.models import Conversation
        from api.providers.models import AIProvider

        provider = AIProvider.objects.create(name="OpenAI")
        llm = LanguageModel.objects.create(
            provider=provider,
            slug="gpt-test-meta",
            name="GPT Test",
        )
        agent = Agent.objects.create(
            name="Test Agent",
            salute="hi",
            act_as="help",
            user=user,
            llm=llm,
            model_slug=llm.slug,
            model_provider="openai",
        )
        conv = Conversation.objects.create(user=user)

        response = client.post(
            "/v1/ai_layers/agent-task/conversation/",
            {
                "conversation_id": str(conv.id),
                "agent_slugs": [agent.slug],
                "user_inputs": [{"type": "input_text", "text": "hello"}],
                "tool_names": [],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 202, response.json() if response.status_code != 202 else "")
        conv.refresh_from_db()
        self.assertEqual(conv.metadata.get("related_agents"), [{"id": agent.id}])
