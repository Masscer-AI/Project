"""Tests for schedule_task helpers, tools, and fire path."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from api.ai_layers.models import Agent
from api.ai_layers.tools.calendar_tool_helpers import resolve_org_timezone
from api.authenticate.models import Organization, UserProfile
from api.messaging.models import Conversation, ConversationTakeover, ScheduledConversationTask
from api.messaging.schedule_helpers import (
    build_cron_from_structured,
    compute_next_run_at,
    mon0_to_cron_dow,
    parse_run_at_to_utc,
    resolve_cron_expression,
)


class ScheduleHelperTests(SimpleTestCase):
    def test_parse_run_at_naive_uses_org_timezone(self):
        utc = parse_run_at_to_utc("2026-07-27T11:00:00", "America/Guayaquil")
        # Guayaquil is UTC-5 → 16:00 UTC
        self.assertEqual(utc, datetime(2026, 7, 27, 16, 0, 0, tzinfo=ZoneInfo("UTC")))

    def test_parse_run_at_with_offset(self):
        utc = parse_run_at_to_utc("2026-07-27T11:00:00-05:00", "UTC")
        self.assertEqual(utc, datetime(2026, 7, 27, 16, 0, 0, tzinfo=ZoneInfo("UTC")))

    def test_weekly_cron_monday_conversion(self):
        self.assertEqual(mon0_to_cron_dow(0), 1)  # Mon
        self.assertEqual(mon0_to_cron_dow(6), 0)  # Sun
        cron = build_cron_from_structured(
            recurrence="weekly",
            time_of_day="11:00",
            weekdays=[0],
        )
        self.assertEqual(cron, "0 11 * * 1")

    def test_compute_next_weekly_monday_11(self):
        # Fixed: Sunday 2026-07-26 12:00 Guayaquil
        after = datetime(2026, 7, 26, 17, 0, 0, tzinfo=ZoneInfo("UTC"))
        cron = resolve_cron_expression(
            schedule_type="recurring",
            recurrence="weekly",
            time_of_day="11:00",
            weekdays=[0],
        )
        next_run = compute_next_run_at(
            schedule_type="recurring",
            tz_name="America/Guayaquil",
            cron=cron,
            after=after,
        )
        local = next_run.astimezone(ZoneInfo("America/Guayaquil"))
        self.assertEqual(local.weekday(), 0)  # Monday
        self.assertEqual(local.hour, 11)
        self.assertEqual(local.minute, 0)

    def test_cron_escape_hatch(self):
        cron = resolve_cron_expression(
            schedule_type="recurring",
            cron="30 9 * * 1-5",
        )
        self.assertEqual(cron, "30 9 * * 1-5")
        after = datetime(2026, 7, 20, 12, 0, 0, tzinfo=ZoneInfo("UTC"))
        next_run = compute_next_run_at(
            schedule_type="recurring",
            tz_name="America/Guayaquil",
            cron=cron,
            after=after,
        )
        local = next_run.astimezone(ZoneInfo("America/Guayaquil"))
        self.assertEqual(local.hour, 9)
        self.assertEqual(local.minute, 30)

    def test_once_rejects_past(self):
        past = datetime(2020, 1, 1, 12, 0, 0, tzinfo=ZoneInfo("UTC"))
        with self.assertRaises(ValueError):
            compute_next_run_at(
                schedule_type="once",
                tz_name="UTC",
                run_at_utc=past,
                after=datetime(2026, 1, 1, tzinfo=ZoneInfo("UTC")),
            )


class ScheduleToolRegistryTests(SimpleTestCase):
    def test_schedule_tools_registered(self):
        from api.ai_layers.tools import SCHEDULE_AGENT_TOOL_NAMES, list_available_tools

        names = list_available_tools()
        for tool in SCHEDULE_AGENT_TOOL_NAMES:
            self.assertIn(tool, names)


class ScheduleTaskToolTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="sched", email="sched@test.com", password="x"
        )
        self.org = Organization.objects.create(
            name="Org", owner=self.user, timezone="America/Guayaquil"
        )
        UserProfile.objects.create(user=self.user, organization=self.org, name="Sched")
        self.agent = Agent.objects.create(
            name="Sched Agent",
            salute="hi",
            act_as="help",
            user=self.user,
            organization=self.org,
        )
        self.conversation = Conversation.objects.create(
            user=self.user,
            organization=self.org,
        )

    @patch("api.messaging.tasks.run_scheduled_conversation_task.apply_async")
    def test_schedule_once_create(self, mock_apply):
        mock_apply.return_value = MagicMock(id="celery-once-1")
        from api.ai_layers.tools.schedule_task import _schedule_task_impl

        future_local = (
            datetime.now(ZoneInfo("America/Guayaquil")) + timedelta(days=2)
        ).replace(hour=11, minute=0, second=0, microsecond=0)
        result = _schedule_task_impl(
            instruction="Write a weekly competitor report and email it to all members.",
            schedule_type="once",
            conversation_id=str(self.conversation.id),
            organization_id=self.org.id,
            user_id=self.user.id,
            agent_slugs=[self.agent.slug],
            multiagentic_modality="isolated",
            run_at=future_local.strftime("%Y-%m-%dT%H:%M:%S"),
        )
        self.assertTrue(result.success)
        self.assertEqual(result.timezone, "America/Guayaquil")
        self.assertIn("Once at", result.schedule_summary or "")
        task = ScheduledConversationTask.objects.get(id=result.task_id)
        self.assertEqual(task.status, ScheduledConversationTask.Status.PENDING)
        self.assertEqual(task.agent_slugs, [self.agent.slug])
        self.assertEqual(task.celery_task_id, "celery-once-1")
        mock_apply.assert_called_once()

    @patch("api.messaging.tasks.run_scheduled_conversation_task.apply_async")
    def test_schedule_weekly_and_cancel(self, mock_apply):
        mock_apply.return_value = MagicMock(id="celery-weekly-1")
        from api.ai_layers.tools.cancel_scheduled_task import _cancel_scheduled_task_impl
        from api.ai_layers.tools.list_scheduled_tasks import _list_scheduled_tasks_impl
        from api.ai_layers.tools.schedule_task import _schedule_task_impl

        result = _schedule_task_impl(
            instruction="Send the morning status docx to all organization members.",
            schedule_type="recurring",
            conversation_id=str(self.conversation.id),
            organization_id=self.org.id,
            user_id=self.user.id,
            agent_slugs=[self.agent.slug],
            multiagentic_modality="isolated",
            recurrence="weekly",
            time_of_day="11:00",
            weekdays=[0],
        )
        self.assertTrue(result.success)
        listed = _list_scheduled_tasks_impl(
            conversation_id=str(self.conversation.id),
            organization_id=self.org.id,
        )
        self.assertEqual(listed.count, 1)
        self.assertEqual(listed.tasks[0]["id"], result.task_id)

        with patch("api.celery.app.control.revoke") as mock_revoke:
            cancelled = _cancel_scheduled_task_impl(
                task_id=result.task_id,
                conversation_id=str(self.conversation.id),
                organization_id=self.org.id,
            )
        self.assertTrue(cancelled.success)
        mock_revoke.assert_called_once_with("celery-weekly-1", terminate=False)
        task = ScheduledConversationTask.objects.get(id=result.task_id)
        self.assertEqual(task.status, ScheduledConversationTask.Status.CANCELLED)

    def test_resolve_org_timezone(self):
        self.assertEqual(resolve_org_timezone(self.org.id), "America/Guayaquil")


class ScheduleFirePathTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="fire", email="fire@test.com", password="x"
        )
        self.org = Organization.objects.create(
            name="Fire Org", owner=self.user, timezone="America/Guayaquil"
        )
        UserProfile.objects.create(user=self.user, organization=self.org, name="Fire")
        self.agent = Agent.objects.create(
            name="Fire Agent",
            salute="hi",
            act_as="help",
            user=self.user,
            organization=self.org,
        )
        self.conversation = Conversation.objects.create(
            user=self.user,
            organization=self.org,
        )

    def _make_pending(self, **kwargs):
        defaults = dict(
            conversation=self.conversation,
            organization=self.org,
            created_by=self.user,
            instruction_text="Write a short status update.",
            schedule_type=ScheduledConversationTask.ScheduleType.ONCE,
            timezone="America/Guayaquil",
            run_at=timezone.now() - timedelta(minutes=1),
            next_run_at=timezone.now() - timedelta(minutes=1),
            status=ScheduledConversationTask.Status.PENDING,
            agent_slugs=[self.agent.slug],
            multiagentic_modality="isolated",
        )
        defaults.update(kwargs)
        return ScheduledConversationTask.objects.create(**defaults)

    @patch("api.ai_layers.tasks.conversation_agent_task")
    def test_fire_invokes_agent_task_with_metadata(self, mock_agent):
        mock_agent.return_value = {
            "status": "completed",
            "user_message_id": 42,
            "message_id": 99,
        }
        task = self._make_pending()
        from api.messaging.tasks import run_scheduled_conversation_task

        result = run_scheduled_conversation_task(str(task.id))
        self.assertEqual(result["status"], ScheduledConversationTask.Status.DONE)
        mock_agent.assert_called_once()
        kwargs = mock_agent.call_args.kwargs
        self.assertEqual(
            kwargs["user_inputs"],
            [{"type": "input_text", "text": "Write a short status update."}],
        )
        self.assertEqual(
            kwargs["user_message_metadata"],
            {"source": "scheduled_task", "scheduled_task_id": str(task.id)},
        )
        self.assertEqual(kwargs["agent_slugs"], [self.agent.slug])
        task.refresh_from_db()
        self.assertEqual(task.status, ScheduledConversationTask.Status.DONE)
        self.assertEqual(task.created_message_id, 42)

    @patch("api.ai_layers.tasks.conversation_agent_task")
    def test_fire_skips_takeover(self, mock_agent):
        task = self._make_pending()
        ConversationTakeover.objects.create(
            conversation=self.conversation,
            user=self.user,
            status=ConversationTakeover.Status.ACTIVE,
        )
        from api.messaging.tasks import run_scheduled_conversation_task

        result = run_scheduled_conversation_task(str(task.id))
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "takeover_active")
        mock_agent.assert_not_called()
        task.refresh_from_db()
        self.assertEqual(task.status, ScheduledConversationTask.Status.PENDING)
        self.assertGreater(task.next_run_at, timezone.now())

    @patch("api.messaging.tasks.run_scheduled_conversation_task.delay")
    def test_catch_up_enqueues_overdue(self, mock_delay):
        due = self._make_pending()
        future = self._make_pending(
            next_run_at=timezone.now() + timedelta(hours=2),
            run_at=timezone.now() + timedelta(hours=2),
            instruction_text="Future task",
        )
        from api.messaging.tasks import run_due_scheduled_conversation_tasks

        out = run_due_scheduled_conversation_tasks()
        self.assertEqual(out["enqueued"], 1)
        mock_delay.assert_called_once_with(str(due.id))
        self.assertNotEqual(str(future.id), str(due.id))

    @patch("api.messaging.tasks.enqueue_scheduled_conversation_task")
    @patch("api.ai_layers.tasks.conversation_agent_task")
    def test_recurring_advances_after_fire(self, mock_agent, mock_enqueue):
        mock_agent.return_value = {"status": "completed", "user_message_id": 7}
        cron = "0 11 * * 1"
        task = self._make_pending(
            schedule_type=ScheduledConversationTask.ScheduleType.RECURRING,
            recurrence=ScheduledConversationTask.Recurrence.WEEKLY,
            time_of_day="11:00",
            weekdays=[0],
            cron=cron,
            run_at=None,
        )
        from api.messaging.tasks import run_scheduled_conversation_task

        result = run_scheduled_conversation_task(str(task.id))
        self.assertIn(result["status"], ("completed", "completed_with_error"))
        task.refresh_from_db()
        self.assertEqual(task.status, ScheduledConversationTask.Status.PENDING)
        self.assertGreater(task.next_run_at, timezone.now())
        mock_enqueue.assert_called_once()


class ScheduledTasksApiTests(TestCase):
    def setUp(self):
        from api.authenticate.models import Token
        from rest_framework.test import APIClient

        self.client = APIClient()
        self.user = User.objects.create_user(
            username="api_sched", email="api_sched@test.com", password="x"
        )
        self.stranger = User.objects.create_user(
            username="stranger", email="stranger@test.com", password="x"
        )
        self.org = Organization.objects.create(
            name="API Org", owner=self.user, timezone="America/Guayaquil"
        )
        UserProfile.objects.create(user=self.user, organization=self.org, name="API")
        self.conversation = Conversation.objects.create(
            user=self.user,
            organization=self.org,
        )
        self.token, _ = Token.get_or_create(user=self.user, token_type="login")
        self.stranger_token, _ = Token.get_or_create(
            user=self.stranger, token_type="login"
        )
        self.pending = ScheduledConversationTask.objects.create(
            conversation=self.conversation,
            organization=self.org,
            created_by=self.user,
            instruction_text="Pending instruction",
            schedule_type=ScheduledConversationTask.ScheduleType.ONCE,
            timezone="America/Guayaquil",
            run_at=timezone.now() + timedelta(days=1),
            next_run_at=timezone.now() + timedelta(days=1),
            status=ScheduledConversationTask.Status.PENDING,
            agent_slugs=["agent"],
            celery_task_id="celery-api-1",
        )
        self.done = ScheduledConversationTask.objects.create(
            conversation=self.conversation,
            organization=self.org,
            created_by=self.user,
            instruction_text="Done instruction",
            schedule_type=ScheduledConversationTask.ScheduleType.ONCE,
            timezone="America/Guayaquil",
            run_at=timezone.now() - timedelta(days=1),
            next_run_at=timezone.now() - timedelta(days=1),
            status=ScheduledConversationTask.Status.DONE,
            agent_slugs=["agent"],
        )

    def _auth(self, token):
        return {"HTTP_AUTHORIZATION": f"Token {token.key}"}

    def test_list_excludes_finished_by_default(self):
        response = self.client.get(
            f"/v1/messaging/conversations/{self.conversation.id}/scheduled-tasks/",
            **self._auth(self.token),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["tasks"][0]["id"], str(self.pending.id))

    def test_list_include_finished(self):
        response = self.client.get(
            f"/v1/messaging/conversations/{self.conversation.id}/scheduled-tasks/"
            "?include_finished=true",
            **self._auth(self.token),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 2)

    def test_list_denied_for_foreign_user(self):
        response = self.client.get(
            f"/v1/messaging/conversations/{self.conversation.id}/scheduled-tasks/",
            **self._auth(self.stranger_token),
        )
        self.assertEqual(response.status_code, 404)

    @patch("api.celery.app.control.revoke")
    def test_cancel_flips_status(self, mock_revoke):
        response = self.client.delete(
            f"/v1/messaging/scheduled-tasks/{self.pending.id}/",
            **self._auth(self.token),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.pending.refresh_from_db()
        self.assertEqual(
            self.pending.status, ScheduledConversationTask.Status.CANCELLED
        )
        mock_revoke.assert_called_once_with("celery-api-1", terminate=False)

    def test_cancel_denied_for_foreign_user(self):
        response = self.client.delete(
            f"/v1/messaging/scheduled-tasks/{self.pending.id}/",
            **self._auth(self.stranger_token),
        )
        self.assertEqual(response.status_code, 404)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, ScheduledConversationTask.Status.PENDING)

    def test_list_my_scheduled_tasks_across_conversations(self):
        other_conv = Conversation.objects.create(
            user=self.user,
            organization=self.org,
            title="Other thread",
        )
        ScheduledConversationTask.objects.create(
            conversation=other_conv,
            organization=self.org,
            created_by=self.user,
            instruction_text="Other instruction",
            schedule_type=ScheduledConversationTask.ScheduleType.ONCE,
            timezone="America/Guayaquil",
            run_at=timezone.now() + timedelta(days=2),
            next_run_at=timezone.now() + timedelta(days=2),
            status=ScheduledConversationTask.Status.PENDING,
            agent_slugs=["agent"],
        )
        # Stranger's task must not appear
        stranger_conv = Conversation.objects.create(
            user=self.stranger,
            title="Stranger",
        )
        ScheduledConversationTask.objects.create(
            conversation=stranger_conv,
            organization=self.org,
            created_by=self.stranger,
            instruction_text="Stranger task",
            schedule_type=ScheduledConversationTask.ScheduleType.ONCE,
            timezone="UTC",
            run_at=timezone.now() + timedelta(days=1),
            next_run_at=timezone.now() + timedelta(days=1),
            status=ScheduledConversationTask.Status.PENDING,
            agent_slugs=["agent"],
        )

        response = self.client.get(
            "/v1/messaging/scheduled-tasks/",
            **self._auth(self.token),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 2)
        ids = {t["id"] for t in data["tasks"]}
        self.assertIn(str(self.pending.id), ids)
        self.assertTrue(any(t.get("conversation_id") for t in data["tasks"]))
