from django.test import SimpleTestCase


class PlatformAssignmentToolsRegistryTests(SimpleTestCase):
    def test_assignment_tools_registered(self):
        from api.ai_layers.platform_tools import list_platform_tools

        names = list_platform_tools()
        self.assertIn("create_user_assignment", names)
        self.assertIn("list_user_assignments", names)
        self.assertIn("read_masscer_instructions", names)

    def test_read_masscer_instructions_returns_catalog(self):
        from api.ai_layers.tools.read_masscer_instructions import (
            _read_masscer_instructions_impl,
        )

        result = _read_masscer_instructions_impl()
        nav_keys = {n.key for n in result.navigate_targets}
        focus_keys = {f.key for f in result.focus_targets}
        self.assertIn("organization_members", nav_keys)
        self.assertIn("agents-modal-trigger", focus_keys)
        self.assertTrue(result.rules)
