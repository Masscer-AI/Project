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
