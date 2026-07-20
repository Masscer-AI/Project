"""Tests for Google Calendar agent tools and time helpers."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from api.ai_layers.tools.calendar_tool_helpers import (
    google_event_time,
    resolve_guest_emails,
    window_for_timeframe,
)
from api.authenticate.models import Organization, UserProfile


class CalendarTimeframeTests(SimpleTestCase):
    def test_today_window_america_guayaquil(self):
        tz = "America/Guayaquil"
        fixed = datetime(2026, 7, 20, 15, 30, 0, tzinfo=ZoneInfo(tz))
        t_min, t_max = window_for_timeframe(
            timeframe="today",
            tz_name=tz,
            now=fixed,
        )
        self.assertTrue(t_min.startswith("2026-07-20T00:00:00"))
        self.assertTrue(t_max.startswith("2026-07-21T00:00:00"))

    def test_google_event_time_naive_uses_timezone(self):
        payload = google_event_time("2026-07-22T15:00:00", "America/Guayaquil")
        self.assertEqual(payload["dateTime"], "2026-07-22T15:00:00")
        self.assertEqual(payload["timeZone"], "America/Guayaquil")


class CalendarToolRegistryTests(SimpleTestCase):
    def test_calendar_tools_registered(self):
        from api.ai_layers.tools import list_available_tools

        names = list_available_tools()
        for tool in (
            "list_calendar_events",
            "create_calendar_event",
            "update_calendar_event",
        ):
            self.assertIn(tool, names)


class CalendarGuestResolutionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="o1", email="owner@test.com", password="x"
        )
        self.guest = User.objects.create_user(
            username="g1", email="guest@test.com", password="x"
        )
        self.org = Organization.objects.create(name="Org", owner=self.owner)
        UserProfile.objects.create(user=self.guest, organization=self.org, name="Guest")

    def test_resolve_guest_emails(self):
        attendees, skipped = resolve_guest_emails([self.guest.id], self.org)
        self.assertEqual(skipped, 0)
        self.assertEqual(attendees, [{"email": "guest@test.com"}])


class ListCalendarEventsToolTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="cal", email="cal@test.com", password="x"
        )
        self.org = Organization.objects.create(
            name="Org", owner=self.user, timezone="America/Guayaquil"
        )
        UserProfile.objects.create(user=self.user, organization=self.org, name="Cal")
        from api.integrations.models import Integration, IntegrationProvider

        Integration.objects.create(
            user=self.user,
            provider=IntegrationProvider.GOOGLE_CALENDAR,
            access_token="tok",
            metadata={"account_email": "cal@test.com"},
        )

    @patch("api.ai_layers.tools.list_calendar_events.list_events_for_user")
    def test_list_impl_calls_service(self, mock_list):
        mock_list.return_value = [{"id": "e1", "summary": "Meet"}]
        from api.ai_layers.tools.list_calendar_events import _list_calendar_events_impl

        result = _list_calendar_events_impl(
            timeframe="today",
            date=None,
            time_min=None,
            time_max=None,
            max_results=10,
            calendar_id="primary",
            user_id=self.user.id,
            organization_id=self.org.id,
        )
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.timezone, "America/Guayaquil")
        mock_list.assert_called_once()
