from typing import Any
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient


class MasscerHelpCatalogTests(SimpleTestCase):
    def test_help_topics_json_validates(self):
        from api.ai_layers.masscer_help import load_help_topic_catalog, reload_help_topic_catalog_for_tests

        reload_help_topic_catalog_for_tests()
        catalog = load_help_topic_catalog()
        self.assertGreaterEqual(catalog.version, 1)
        self.assertGreater(len(catalog.topics), 0)
        invite = catalog.by_id("invite_user")
        self.assertIsNotNone(invite)
        self.assertIn("activeTab=members", invite.build_app_url())

    def test_platform_tools_include_masscer_help(self):
        from api.ai_layers.platform_tools import list_platform_tools

        names = list_platform_tools()
        self.assertIn("get_masscer_help_topic", names)
        self.assertIn("list_masscer_help_topics", names)


class MasscerHelpTopicToolTests(TestCase):
    def test_get_masscer_help_topic_returns_url_and_steps(self):
        from api.ai_layers.tools.get_masscer_help_topic import _get_masscer_help_topic_impl

        result = _get_masscer_help_topic_impl("invite_user", user_id=None)
        self.assertEqual(result.id, "invite_user")
        self.assertIn("/organization", result.app_url)
        self.assertGreater(len(result.steps), 0)
        self.assertTrue(result.access_allowed)

    def test_list_masscer_help_topics(self):
        from api.ai_layers.tools.list_masscer_help_topics import _list_masscer_help_topics_impl

        result = _list_masscer_help_topics_impl()
        ids = {t.id for t in result.topics}
        self.assertIn("invite_user", ids)
        self.assertIn("create_agent", ids)


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
        self.assertIn("create_completion", names)
        self.assertIn("generate_document_file", names)

    def test_document_maker_plugin_removed(self):
        from api.ai_layers.plugins.registry import PLUGIN_DEFINITIONS

        self.assertNotIn("document-maker", PLUGIN_DEFINITIONS)


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


class VertexGeminiAgentLoopParallelFunctionCallTests(SimpleTestCase):
    def test_parallel_tool_responses_batched_in_single_user_turn(self):
        from google.genai import types as genai_types

        from api.ai_layers.vertex_gemini_agent_loop import VertexGeminiAgentLoop

        fc1 = genai_types.FunctionCall(name="tool_a", args={"x": 1})
        fc2 = genai_types.FunctionCall(name="tool_b", args={"y": 2})
        parallel_model_turn = genai_types.Content(
            role="model",
            parts=[
                genai_types.Part(function_call=fc1),
                genai_types.Part(function_call=fc2),
            ],
        )
        parallel_response = Mock()
        parallel_response.candidates = [Mock(content=parallel_model_turn)]
        parallel_response.usage_metadata = None

        final_model_turn = genai_types.Content(
            role="model",
            parts=[genai_types.Part.from_text(text="Done")],
        )
        final_response = Mock()
        final_response.candidates = [Mock(content=final_model_turn)]
        final_response.usage_metadata = None

        captured_contents: list[list[Any]] = []

        def fake_generate(*, model, contents, config):
            captured_contents.append(list(contents))
            if len(captured_contents) == 1:
                return parallel_response
            return final_response

        mock_client = Mock()
        mock_client.models.generate_content.side_effect = fake_generate

        def tool_a(**_kwargs):
            return {"ok": True, "tool": "a"}

        def tool_b(**_kwargs):
            return {"ok": True, "tool": "b"}

        schema = {"type": "object", "properties": {}}
        loop = VertexGeminiAgentLoop(
            tools=[
                {
                    "name": "tool_a",
                    "description": "tool a",
                    "parameters": schema,
                    "function": tool_a,
                },
                {
                    "name": "tool_b",
                    "description": "tool b",
                    "parameters": schema,
                    "function": tool_b,
                },
            ],
            instructions="test",
            model="gemini-test",
        )

        with patch(
            "api.ai_layers.vertex_gemini_agent_loop.VertexGeminiText"
        ) as mock_vx_cls:
            mock_vx_cls.return_value._get_client.return_value = mock_client
            result = loop.run([{"role": "user", "content": "run tools"}])

        self.assertEqual(result.output, "Done")
        self.assertEqual(len(captured_contents), 2)

        follow_up_contents = captured_contents[1]
        user_turns_with_function_responses = [
            c
            for c in follow_up_contents
            if getattr(c, "role", None) == "user"
            and any(
                getattr(p, "function_response", None) is not None
                for p in (getattr(c, "parts", None) or [])
            )
        ]
        self.assertEqual(len(user_turns_with_function_responses), 1)
        fr_parts = [
            p
            for p in user_turns_with_function_responses[0].parts
            if getattr(p, "function_response", None) is not None
        ]
        self.assertEqual(len(fr_parts), 2)
        names = {p.function_response.name for p in fr_parts}
        self.assertEqual(names, {"tool_a", "tool_b"})


class ToolAttachmentExtractionTests(SimpleTestCase):
    def test_extract_render_document_template_attachments(self):
        from api.ai_layers.tasks import _extract_render_document_template_attachments

        tool_calls = [
            {
                "tool_name": "render_document_template",
                "result": (
                    '{"attachment_id":"7b2a85f8-0b74-4a0f-b5a0-548df74dc5be",'
                    '"name":"contract.docx","content":"https://example.com/contract.docx"}'
                ),
            },
            {
                "tool_name": "create_image",
                "result": '{"attachment_id":"ignore","content":"https://example.com/image.png"}',
            },
        ]

        attachments, attachment_ids = _extract_render_document_template_attachments(tool_calls)

        self.assertEqual(
            attachments,
            [
                {
                    "type": "document",
                    "content": "https://example.com/contract.docx",
                    "name": "contract.docx",
                    "attachment_id": "7b2a85f8-0b74-4a0f-b5a0-548df74dc5be",
                }
            ],
        )
        self.assertEqual(attachment_ids, ["7b2a85f8-0b74-4a0f-b5a0-548df74dc5be"])

    def test_extract_generate_document_file_attachments(self):
        from api.ai_layers.tasks import _extract_generate_document_file_attachments

        tool_calls = [
            {
                "tool_name": "generate_document_file",
                "result": (
                    '{"attachment_id":"a1b2c3d4-e5f6-7890-abcd-ef1234567890",'
                    '"name":"report.docx","content":"https://example.com/report.docx"}'
                ),
            },
            {
                "tool_name": "render_document_template",
                "result": '{"attachment_id":"x","content":"https://example.com/x.docx"}',
            },
        ]

        attachments, attachment_ids = _extract_generate_document_file_attachments(
            tool_calls
        )

        self.assertEqual(
            attachments,
            [
                {
                    "type": "document",
                    "content": "https://example.com/report.docx",
                    "name": "report.docx",
                    "attachment_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                }
            ],
        )
        self.assertEqual(
            attachment_ids, ["a1b2c3d4-e5f6-7890-abcd-ef1234567890"]
        )

    def test_extract_generate_excel_file_attachments(self):
        from api.ai_layers.tasks import _extract_generate_excel_file_attachments

        tool_calls = [
            {
                "tool_name": "generate_excel_file",
                "result": (
                    '{"attachment_id":"b2c3d4e5-f6a7-8901-bcde-f12345678901",'
                    '"name":"budget.xlsx","content":"https://example.com/budget.xlsx"}'
                ),
            }
        ]

        attachments, attachment_ids = _extract_generate_excel_file_attachments(
            tool_calls
        )

        self.assertEqual(
            attachments,
            [
                {
                    "type": "document",
                    "content": "https://example.com/budget.xlsx",
                    "name": "budget.xlsx",
                    "attachment_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                }
            ],
        )
        self.assertEqual(
            attachment_ids, ["b2c3d4e5-f6a7-8901-bcde-f12345678901"]
        )


class GenerateDocumentFileToolTests(SimpleTestCase):
    @patch("api.ai_layers.models.Agent")
    @patch("api.messaging.models.MessageAttachment")
    @patch("api.utils.document_tools.convert_document_string_to_docx_bytes")
    @patch("api.messaging.models.Conversation")
    def test_impl_creates_attachment(
        self, mock_conversation_cls, mock_convert, mock_attachment_cls, mock_agent
    ):
        from api.ai_layers.tools.generate_document_file import _generate_document_file_impl

        mock_conversation_cls.objects.select_related.return_value.get.return_value = (
            Mock(id="conv-1")
        )
        mock_convert.return_value = b"docx-bytes"
        att = Mock()
        att.id = "att-uuid"
        att.file.url = "/media/message_attachments/2026/05/report.docx"
        mock_attachment_cls.objects.create.return_value = att

        result = _generate_document_file_impl(
            document_string="# Title\n\nBody",
            extension="md",
            output_filename="report.docx",
            conversation_id="conv-1",
            user_id=None,
            agent_slug="test-agent",
        )

        self.assertEqual(result.attachment_id, "att-uuid")
        self.assertEqual(result.name, "report.docx")
        self.assertIn("report.docx", result.content)
        mock_convert.assert_called_once_with("# Title\n\nBody", "md")
        mock_attachment_cls.objects.create.assert_called_once()


class GenerateExcelFileToolTests(SimpleTestCase):
    @patch("api.ai_layers.models.Agent")
    @patch("api.messaging.models.MessageAttachment")
    @patch("api.utils.spreadsheet_tools.build_xlsx_bytes_from_sheets")
    @patch("api.messaging.models.Conversation")
    def test_impl_creates_attachment(
        self, mock_conversation_cls, mock_build, mock_attachment_cls, mock_agent
    ):
        from api.ai_layers.tools.generate_excel_file import _generate_excel_file_impl

        mock_conversation_cls.objects.select_related.return_value.get.return_value = (
            Mock(id="conv-1")
        )
        mock_build.return_value = b"PK\x03\x04fake-xlsx"
        att = Mock()
        att.id = "att-uuid"
        att.file.url = "/media/message_attachments/2026/05/budget.xlsx"
        mock_attachment_cls.objects.create.return_value = att

        result = _generate_excel_file_impl(
            sheets_json='[{"name":"Sales","headers":["Month"],"rows":[["Jan"]]}]',
            output_filename="budget.xlsx",
            conversation_id="conv-1",
            user_id=None,
            agent_slug="test-agent",
        )

        self.assertEqual(result.attachment_id, "att-uuid")
        self.assertEqual(result.name, "budget.xlsx")
        self.assertIn("budget.xlsx", result.content)
        mock_build.assert_called_once()
        mock_attachment_cls.objects.create.assert_called_once()

    def test_generate_excel_file_is_registered(self):
        from api.ai_layers.tools import list_available_tools

        self.assertIn("generate_excel_file", list_available_tools())


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

    @patch("api.ai_layers.views.conversation_agent_task.delay")
    @patch("api.ai_layers.views.handle_inbound_during_takeover")
    @patch("api.ai_layers.views.get_active_takeover")
    def test_post_skips_agent_and_persists_inbound_when_takeover_active(
        self, mock_get_takeover, mock_handle_takeover, mock_delay
    ):
        mock_delay.return_value = Mock(id="celery-task-1")
        user = User.objects.create_user(username="u2", email="u2@e.com", password="x")
        client = APIClient()
        client.force_authenticate(user=user)

        from api.ai_layers.models import Agent, LanguageModel
        from api.messaging.models import Conversation
        from api.providers.models import AIProvider

        provider = AIProvider.objects.create(name="OpenAI-2")
        llm = LanguageModel.objects.create(
            provider=provider,
            slug="gpt-test-meta-2",
            name="GPT Test 2",
        )
        agent = Agent.objects.create(
            name="Test Agent 2",
            salute="hi",
            act_as="help",
            user=user,
            llm=llm,
            model_slug=llm.slug,
            model_provider="openai",
        )
        conv = Conversation.objects.create(user=user)
        mock_takeover = Mock(user_id=999, status="ACTIVE")
        mock_get_takeover.return_value = mock_takeover

        payload = {
            "conversation_id": str(conv.id),
            "agent_slugs": [agent.slug],
            "user_inputs": [{"type": "input_text", "text": "hello takeover"}],
            "tool_names": [],
        }
        response = client.post(
            "/v1/ai_layers/agent-task/conversation/",
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            202,
            response.json() if response.status_code != 202 else "",
        )
        self.assertEqual(response.json().get("takeover"), True)
        self.assertEqual(response.json().get("agent_skipped"), True)
        mock_get_takeover.assert_called_once_with(conv)
        mock_handle_takeover.assert_called_once()
        mock_delay.assert_not_called()


class CreateCompletionToolTests(TestCase):
    @patch("api.authenticate.services.FeatureFlagService.is_feature_enabled")
    def test_create_completion_saves_pending(self, mock_ff):
        mock_ff.return_value = (True, "ok")
        from api.ai_layers.tools.create_completion import _create_completion_impl
        from api.ai_layers.models import Agent, LanguageModel
        from api.messaging.models import Conversation
        from api.providers.models import AIProvider
        from api.finetuning.models import Completion, CompletionAssignment

        user = User.objects.create_user(username="ccu", email="ccu@e.com", password="x")
        provider = AIProvider.objects.create(name="OpenAI-cc")
        llm = LanguageModel.objects.create(provider=provider, slug="gpt-cc", name="GPT")
        agent = Agent.objects.create(
            name="CCA",
            salute="h",
            act_as="h",
            user=user,
            llm=llm,
            model_slug=llm.slug,
            model_provider="openai",
        )
        conv = Conversation.objects.create(user=user)

        result = _create_completion_impl(
            prompt="What is X?",
            answer="X is Y.",
            user_id=user.id,
            agent_slug=agent.slug,
            conversation_id=str(conv.id),
        )
        self.assertFalse(result.approved)
        c = Completion.objects.get(id=result.completion_id)
        self.assertEqual(c.prompt, "What is X?")
        self.assertEqual(c.answer, "X is Y.")
        self.assertFalse(c.approved)
        self.assertTrue(
            CompletionAssignment.objects.filter(completion=c, agent=agent).exists()
        )

    @patch("api.authenticate.services.FeatureFlagService.is_feature_enabled")
    def test_create_completion_requires_train_agents_flag(self, mock_ff):
        mock_ff.return_value = (False, "no")
        from api.ai_layers.tools.create_completion import _create_completion_impl
        from api.ai_layers.models import Agent, LanguageModel
        from api.messaging.models import Conversation
        from api.providers.models import AIProvider

        user = User.objects.create_user(username="ccu2", email="ccu2@e.com", password="x")
        provider = AIProvider.objects.create(name="OpenAI-cc2")
        llm = LanguageModel.objects.create(provider=provider, slug="gpt-cc2", name="GPT")
        agent = Agent.objects.create(
            name="CCA2",
            salute="h",
            act_as="h",
            user=user,
            llm=llm,
            model_slug=llm.slug,
            model_provider="openai",
        )
        conv = Conversation.objects.create(user=user)

        with self.assertRaises(ValueError) as ctx:
            _create_completion_impl(
                prompt="P",
                answer="A",
                user_id=user.id,
                agent_slug=agent.slug,
                conversation_id=str(conv.id),
            )
        self.assertIn("train-agents", str(ctx.exception).lower())

    def test_extract_create_completion_refs_from_tool_calls(self):
        import json

        from api.ai_layers.tasks import _extract_create_completion_refs_from_tool_calls
        from api.ai_layers.models import Agent, LanguageModel
        from api.providers.models import AIProvider
        from api.finetuning.models import Completion, CompletionAssignment

        user = User.objects.create_user(username="ccu3", email="ccu3@e.com", password="x")
        provider = AIProvider.objects.create(name="OpenAI-cc3")
        llm = LanguageModel.objects.create(provider=provider, slug="gpt-cc3", name="GPT")
        agent = Agent.objects.create(
            name="CCA3",
            salute="h",
            act_as="h",
            user=user,
            llm=llm,
            model_slug=llm.slug,
            model_provider="openai",
        )
        c = Completion.objects.create(prompt="p", answer="a", approved=False)
        CompletionAssignment.objects.create(completion=c, agent=agent)
        tool_calls = [
            {
                "tool_name": "create_completion",
                "result": json.dumps(
                    {"completion_id": c.id, "approved": False, "message": "ok"}
                ),
            }
        ]
        atts = _extract_create_completion_refs_from_tool_calls(tool_calls)
        self.assertEqual(len(atts), 1)
        self.assertEqual(atts[0]["type"], "completion")
        self.assertEqual(atts[0]["completion_id"], c.id)

    def test_extract_referenced_completions_from_text(self):
        from api.ai_layers.tasks import _extract_referenced_completions_from_text
        from api.ai_layers.models import Agent, LanguageModel
        from api.providers.models import AIProvider
        from api.finetuning.models import Completion, CompletionAssignment

        user = User.objects.create_user(username="ccu4", email="ccu4@e.com", password="x")
        provider = AIProvider.objects.create(name="OpenAI-cc4")
        llm = LanguageModel.objects.create(provider=provider, slug="gpt-cc4", name="GPT")
        agent = Agent.objects.create(
            name="CCA4",
            salute="h",
            act_as="h",
            user=user,
            llm=llm,
            model_slug=llm.slug,
            model_provider="openai",
        )
        c = Completion.objects.create(prompt="long prompt " * 20, answer="a", approved=False)
        CompletionAssignment.objects.create(completion=c, agent=agent)
        text = f"Edit [here](completion:{c.id})"
        atts = _extract_referenced_completions_from_text(text, user)
        self.assertEqual(len(atts), 1)
        self.assertEqual(atts[0]["completion_id"], c.id)
        self.assertEqual(atts[0]["type"], "completion")

    @patch("api.finetuning.models.chroma_client")
    def test_pending_completion_save_does_not_call_upsert(self, mock_chroma):
        from api.ai_layers.models import Agent, LanguageModel
        from api.providers.models import AIProvider
        from api.finetuning.models import Completion, CompletionAssignment

        user = User.objects.create_user(username="ccu5", email="ccu5@e.com", password="x")
        provider = AIProvider.objects.create(name="OpenAI-cc5")
        llm = LanguageModel.objects.create(provider=provider, slug="gpt-cc5", name="GPT")
        agent = Agent.objects.create(
            name="CCA5",
            salute="h",
            act_as="h",
            user=user,
            llm=llm,
            model_slug=llm.slug,
            model_provider="openai",
        )
        c = Completion.objects.create(prompt="p", answer="a", approved=False)
        CompletionAssignment.objects.create(completion=c, agent=agent)
        self.assertFalse(mock_chroma.upsert_chunk.called)


class WhatsappCrossThreadToolsTests(SimpleTestCase):
    def test_query_conversation_get_tool_whatsapp_org_scoped(self):
        from api.ai_layers.tools.query_conversation import get_tool

        tool = get_tool(
            conversation_id="00000000-0000-4000-8000-000000000001",
            organization_id=1,
            user_id=None,
            is_whatsapp_visitor=True,
        )
        self.assertEqual(tool["name"], "query_conversation")
        self.assertIsNotNone(tool["function"])
        self.assertIn("organization", tool["description"].lower())


class GetTagContextOrganizationScopeTests(TestCase):
    def setUp(self):
        from api.authenticate.models import Organization
        from api.ai_layers.tools.get_tag_context import _get_tag_context_organization_impl
        from api.messaging.models import Conversation, Tag
        from api.whatsapp.conversations import get_or_create_whatsapp_conversation
        from api.whatsapp.models import WSNumber
        from api.ai_layers.models import Agent

        self._get_tag_context_organization_impl = _get_tag_context_organization_impl
        self.owner = User.objects.create_user(username="tag_ctx_owner", password="x")
        self.org = Organization.objects.create(name="Tag Ctx Org", owner=self.owner)
        self.tag = Tag.objects.create(
            title="Startup IA",
            organization=self.org,
            enabled=True,
        )
        self.agent = Agent.objects.create(
            name="Tag Agent", salute="hi", user=self.owner
        )
        self.app_conv = Conversation.objects.create(
            user=self.owner,
            organization=None,
            title="App thread with tag",
            tags=[self.tag.id],
        )
        self.ws = WSNumber.objects.create(
            user=self.owner,
            organization=self.org,
            agent=self.agent,
            number="5550003333",
            platform_id="pnid-tag-ctx",
        )
        self.wa_conv = get_or_create_whatsapp_conversation(self.ws, "593964105554")

    def test_finds_app_chats_without_conversation_organization_id(self):
        result = self._get_tag_context_organization_impl(
            tag_id=self.tag.id,
            organization_id=self.org.id,
            current_conversation_id=str(self.wa_conv.id),
        )
        ids = {c.conversation_id for c in result.conversations}
        self.assertIn(str(self.app_conv.id), ids)
        self.assertNotIn(str(self.wa_conv.id), ids)


class AgentSessionExecutionLogAccessTests(TestCase):
    def setUp(self):
        from api.authenticate.models import Organization, Token
        from api.ai_layers.models import Agent, AgentSession
        from api.messaging.models import Conversation, Message
        from api.whatsapp.conversations import get_or_create_whatsapp_conversation
        from api.whatsapp.models import WSNumber

        self.client = APIClient()
        self.owner = User.objects.create_user(
            username="exec_log_owner", password="x"
        )
        self.org = Organization.objects.create(name="Exec Log Org", owner=self.owner)
        self.agent = Agent.objects.create(
            name="WA Exec Log", salute="hi", user=self.owner
        )
        self.ws = WSNumber.objects.create(
            user=self.owner,
            organization=self.org,
            agent=self.agent,
            number="5550002222",
            platform_id="pnid-exec-log",
        )
        self.conv = get_or_create_whatsapp_conversation(self.ws, "5493333444555")
        self.assistant = Message.objects.create(
            conversation=self.conv,
            type="assistant",
            text="WhatsApp reply",
        )
        AgentSession.objects.create(
            conversation=self.conv,
            assistant_message=self.assistant,
            event_log=[{"type": "tool_call_start", "tool_name": "rag_query"}],
        )
        self.login_token = Token.objects.create(user=self.owner)

    def test_whatsapp_assistant_message_execution_log_accessible(self):
        res = self.client.get(
            "/api/v1/ai_layers/agent-sessions/execution-log/",
            {"assistant_message_id": self.assistant.id},
            HTTP_AUTHORIZATION=f"Token {self.login_token.key}",
        )
        self.assertEqual(res.status_code, 200, res.content)
        payload = res.json()
        self.assertEqual(len(payload["sessions"]), 1)
        self.assertEqual(len(payload["sessions"][0]["event_log"]), 1)


class PlatformAssistantTests(TestCase):
    def setUp(self):
        from api.authenticate.models import Organization, Token, UserProfile
        from api.ai_layers.models import Agent, AgentKind, LanguageModel
        from api.ai_layers.platform_assistant import provision_platform_assistant
        from api.messaging.models import Conversation
        from api.providers.models import AIProvider

        self.owner = User.objects.create_user(
            username="plat_owner", email="plat_owner@e.com", password="x"
        )
        self.member = User.objects.create_user(
            username="plat_member", email="plat_member@e.com", password="x"
        )
        self.org = Organization.objects.create(name="Platform Org", owner=self.owner)
        UserProfile.objects.update_or_create(
            user=self.member,
            defaults={"organization": self.org},
        )
        self.platform_agent, _ = provision_platform_assistant(self.org)

        provider = AIProvider.objects.create(name="OpenAI-plat")
        self.llm = LanguageModel.objects.create(
            provider=provider, slug="gpt-plat", name="GPT Plat"
        )
        self.conv_agent = Agent.objects.create(
            name="Conv Agent",
            salute="hi",
            act_as="help",
            user=self.owner,
            llm=self.llm,
            model_slug=self.llm.slug,
            model_provider="openai",
        )
        self.conv = Conversation.objects.create(user=self.owner)
        self.owner_token = Token.objects.create(user=self.owner)
        self.member_token = Token.objects.create(user=self.member)
        self.client = APIClient()

    def test_provision_platform_assistant_has_title_prompt(self):
        from api.ai_layers.platform_assistant import (
            PLATFORM_ASSISTANT_CONVERSATION_TITLE_PROMPT,
            provision_platform_assistant,
        )

        agent, _ = provision_platform_assistant(self.org)
        self.assertTrue(agent.conversation_title_prompt)
        self.assertEqual(
            agent.conversation_title_prompt,
            PLATFORM_ASSISTANT_CONVERSATION_TITLE_PROMPT,
        )

    def test_provision_platform_assistant_idempotent(self):
        from api.ai_layers.platform_assistant import provision_platform_assistant

        agent2, created = provision_platform_assistant(self.org)
        self.assertFalse(created)
        self.assertEqual(agent2.id, self.platform_agent.id)
        self.assertEqual(
            Agent.objects.filter(
                organization=self.org,
                agent_kind=AgentKind.PLATFORM_ASSISTANT,
            ).count(),
            1,
        )

    def test_accessible_agents_qs_owner_includes_platform_assistant(self):
        from api.ai_layers.access import accessible_agents_qs

        slugs = set(accessible_agents_qs(self.owner).values_list("slug", flat=True))
        self.assertIn(self.platform_agent.slug, slugs)

    def test_accessible_agents_qs_owner_without_profile_org_includes_platform(self):
        """Org owners must see platform assistant even if profile.organization is unset."""
        from api.authenticate.models import UserProfile
        from api.ai_layers.access import accessible_agents_qs

        UserProfile.objects.filter(user=self.owner).update(organization=None)
        slugs = set(accessible_agents_qs(self.owner).values_list("slug", flat=True))
        self.assertIn(self.platform_agent.slug, slugs)

    @patch("api.authenticate.services.FeatureFlagService.is_feature_enabled")
    def test_accessible_agents_qs_member_excluded_without_flag(self, mock_ff):
        from api.ai_layers.access import accessible_agents_qs

        def _side_effect(name, organization=None, user=None):
            if name == "platform-assistant":
                return False, "not-assigned"
            return False, "not-assigned"

        mock_ff.side_effect = _side_effect
        slugs = set(accessible_agents_qs(self.member).values_list("slug", flat=True))
        self.assertNotIn(self.platform_agent.slug, slugs)

    @patch("api.ai_layers.views.conversation_agent_task.delay")
    def test_conversation_endpoint_rejects_platform_assistant(self, mock_delay):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            "/v1/ai_layers/agent-task/conversation/",
            {
                "conversation_id": str(self.conv.id),
                "agent_slugs": [self.platform_agent.slug],
                "user_inputs": [{"type": "input_text", "text": "hello"}],
                "tool_names": [],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        mock_delay.assert_not_called()

    @patch("api.ai_layers.views.platform_assistant_task.delay")
    def test_platform_endpoint_accepts_owner(self, mock_delay):
        mock_delay.return_value = Mock(id="celery-plat-1")
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            "/v1/ai_layers/agent-task/platform/",
            {
                "conversation_id": str(self.conv.id),
                "agent_slug": self.platform_agent.slug,
                "user_inputs": [{"type": "input_text", "text": "help me onboard"}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 202, response.json())
        mock_delay.assert_called_once()

    @patch("api.authenticate.services.FeatureFlagService.is_feature_enabled")
    def test_platform_endpoint_forbidden_without_flag(self, mock_ff):
        mock_ff.return_value = (False, "not-assigned")
        self.client.force_authenticate(user=self.member)
        response = self.client.post(
            "/v1/ai_layers/agent-task/platform/",
            {
                "conversation_id": str(self.conv.id),
                "agent_slug": self.platform_agent.slug,
                "user_inputs": [{"type": "input_text", "text": "help"}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_put_platform_assistant_forbidden(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.put(
            f"/v1/ai_layers/agents/{self.platform_agent.slug}/",
            {"name": "Hacked"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_unique_platform_assistant_per_org_constraint(self):
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            Agent.objects.create(
                name="Duplicate Platform",
                salute="hi",
                act_as="help",
                organization=self.org,
                agent_kind=AgentKind.PLATFORM_ASSISTANT,
                slug="duplicate-platform-assistant",
                llm=self.llm,
                model_slug=self.llm.slug,
            )
