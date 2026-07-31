"""Tests for agent clock context cascade: user → organization → server."""

from __future__ import annotations

from unittest.mock import patch

from django.test import SimpleTestCase

from api.ai_layers.tasks import _agent_clock_context


class AgentClockContextCascadeTests(SimpleTestCase):
    def test_prefers_client_datetime_over_org(self):
        with patch(
            "api.ai_layers.tools.calendar_tool_helpers.format_org_timezone_clock_line",
            return_value="Organization timezone for calendar scheduling: America/Guayaquil.",
        ):
            text = _agent_clock_context(
                {
                    "local_datetime_long": "Friday, July 31, 2026 at 1:00:00 PM ECT",
                    "timezone": "America/Guayaquil",
                    "utc_iso": "2026-07-31T18:00:00.000Z",
                    "locale": "en-US",
                },
                organization_id=1,
            )
        self.assertIn("User's local date and time (their device):", text)
        self.assertIn("using the user's local clock", text)
        self.assertIn("Organization timezone for calendar scheduling:", text)
        self.assertNotIn("using the organization timezone as the default clock", text)
        self.assertNotIn("current date and time (server)", text.lower())

    def test_falls_back_to_organization_clock_when_no_client(self):
        with (
            patch(
                "api.ai_layers.tools.calendar_tool_helpers.resolve_org_timezone",
                return_value="America/Guayaquil",
            ),
            patch(
                "api.ai_layers.tools.calendar_tool_helpers.format_org_timezone_clock_line",
                return_value="Organization timezone for calendar scheduling: America/Guayaquil.",
            ),
        ):
            text = _agent_clock_context(None, organization_id=1)

        self.assertIn(
            "No client clock was provided; using the organization timezone as the default clock.",
            text,
        )
        self.assertIn(
            "Current date and time in organization timezone (America/Guayaquil):",
            text,
        )
        self.assertIn("Organization IANA timezone: America/Guayaquil.", text)
        self.assertIn("Same instant (UTC, ISO-8601):", text)
        self.assertIn("using the organization clock and timezone above", text)
        self.assertIn("Organization timezone for calendar scheduling:", text)
        self.assertNotIn("current date and time (server)", text.lower())

    def test_empty_client_dict_falls_back_to_organization(self):
        with (
            patch(
                "api.ai_layers.tools.calendar_tool_helpers.resolve_org_timezone",
                return_value="UTC",
            ),
            patch(
                "api.ai_layers.tools.calendar_tool_helpers.format_org_timezone_clock_line",
                return_value="Organization timezone for calendar scheduling: UTC.",
            ),
        ):
            text = _agent_clock_context({}, organization_id=1)
        self.assertIn("using the organization timezone as the default clock", text)
        self.assertNotIn("User's local date and time", text)

    def test_server_last_resort_without_org(self):
        text = _agent_clock_context(None, organization_id=None)
        self.assertIn("The current date and time (server) is", text)
        self.assertIn(
            "No client clock or organization timezone was available",
            text,
        )
        self.assertNotIn("organization timezone as the default clock", text)

    def test_server_fallback_message_without_org_id(self):
        text = _agent_clock_context(None)
        self.assertIn("(server)", text)
        self.assertIn("organization timezone was available", text)
