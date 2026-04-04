from django.test import SimpleTestCase


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
