"""Tests for schedule_task helpers, tools, and fire path."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from api.ai_layers.models import Agent, LanguageModel
from api.ai_layers.tools.calendar_tool_helpers import resolve_org_timezone
from api.authenticate.models import Organization, UserProfile
from api.consumption.models import Currency
from api.messaging.models import Conversation, ConversationTakeover, ScheduledConversationTask
from api.messaging.schedule_helpers import (
    build_cron_from_structured,
    compute_next_run_at,
    mon0_to_cron_dow,
    parse_run_at_to_utc,
    resolve_cron_expression,
)
from api.providers.models import AIProvider

def _seed_llm_and_currency():
    Currency.objects.get_or_create(name="Compute Unit", defaults={"one_usd_is": 1000})
    provider = AIProvider.objects.create(name=f"OpenAI-{LanguageModel.objects.count()}")
    return LanguageModel.objects.create(
        provider=provider,
        slug=f"gpt-sched-{LanguageModel.objects.count()}",
        name="GPT Sched",
    )

class ScheduleHelperTests(SimpleTestCase):
    def test_execution_message_hides_details_in_html_comment(self):
        from api.messaging.schedule_helpers import build_scheduled_task_execution_message
        from types import SimpleNamespace
        from datetime import datetime
        from zoneinfo import ZoneInfo

        task = SimpleNamespace(
            id="11111111-1111-1111-1111-111111111111",
            title="Pedir permiso para imagen",
            instruction_text="1. Usa send_ws_template_message.\n2. Reporta el resultado.",
            schedule_type="once",
            timezone="America/Guayaquil",
            next_run_at=datetime(2026, 7, 31, 18, 51, tzinfo=ZoneInfo("UTC")),
            recurrence=None,
            time_of_day=None,
            weekdays=[],
            day_of_month=None,
            cron=None,
            capabilities=["explore_web", "schedule_task"],
        )
        text = build_scheduled_task_execution_message(task)
        self.assertTrue(text.startswith("Ejecutando tarea: Pedir permiso para imagen"))
        self.assertIn("<!--", text)
        self.assertIn("1. Usa send_ws_template_message.", text)
        self.assertNotIn("schedule_task", text.split("<!--", 1)[0])

    def test_parse_run_at_naive_uses_org_timezone(self):
        utc = parse_run_at_to_utc("2026-07-27T11:00:00", "America/Guayaquil")
        self.assertEqual(utc, datetime(2026, 7, 27, 16, 0, 0, tzinfo=ZoneInfo("UTC")))

    def test_parse_run_at_with_offset(self):
        utc = parse_run_at_to_utc("2026-07-27T11:00:00-05:00", "UTC")
        self.assertEqual(utc, datetime(2026, 7, 27, 16, 0, 0, tzinfo=ZoneInfo("UTC")))

    def test_weekly_cron_monday_conversion(self):
        self.assertEqual(mon0_to_cron_dow(0), 1)
        self.assertEqual(mon0_to_cron_dow(6), 0)
        cron = build_cron_from_structured(
            recurrence="weekly",
            time_of_day="11:00",
            weekdays=[0],
        )
        self.assertEqual(cron, "0 11 * * 1")

    def test_compute_next_weekly_monday_11(self):
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
        self.assertEqual(local.weekday(), 0)
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
        self.llm = _seed_llm_and_currency()
        self.user = User.objects.create_user(
            username="sched", email="sched@test.com", password="x"
        )
        self.org = Organization.objects.create(
            name="Org", owner=self.user, timezone="America/Guayaquil"
        )
        UserProfile.objects.filter(user=self.user).update(
            organization=self.org, name="Sched"
        )
        self.agent = Agent.objects.create(
            name="Sched Agent",
            salute="hi",
            act_as="help",
            user=self.user,
            organization=self.org,
            llm=self.llm,
            model_slug=self.llm.slug,
            model_provider="openai",
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
            title="Weekly competitor report",
            instruction=(
                "1. Research competitors with explore_web. "
                "2. Write a weekly competitor report. "
                "3. Email it to all organization members."
            ),
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
        self.assertEqual(result.title, "Weekly competitor report")
        self.assertIn("Once at", result.schedule_summary or "")
        task = ScheduledConversationTask.objects.get(id=result.task_id)
        self.assertEqual(task.status, ScheduledConversationTask.Status.PENDING)
        self.assertEqual(task.title, "Weekly competitor report")
        self.assertEqual(task.agent_slugs, [self.agent.slug])
        self.assertEqual(task.celery_task_id, "celery-once-1")
        self.assertEqual(task.capabilities, [])
        mock_apply.assert_called_once()

    @patch("api.messaging.tasks.run_scheduled_conversation_task.apply_async")
    def test_schedule_explicit_agent_slugs_can_add_specialists(self, mock_apply):
        mock_apply.return_value = MagicMock(id="celery-agents-1")
        specialist = Agent.objects.create(
            name="Tax Specialist",
            slug="tax-sched-specialist",
            salute="hi",
            act_as="tax",
            description="Tax specialist",
            user=self.user,
            organization=self.org,
            llm=self.llm,
            model_slug=self.llm.slug,
            model_provider="openai",
        )
        from api.ai_layers.tools.schedule_task import _schedule_task_impl

        future_local = (
            datetime.now(ZoneInfo("America/Guayaquil")) + timedelta(days=1)
        ).replace(hour=10, minute=0, second=0, microsecond=0)
        result = _schedule_task_impl(
            title="Multi-agent schedule",
            instruction="1. Legal drafts. 2. Tax reviews.",
            schedule_type="once",
            conversation_id=str(self.conversation.id),
            organization_id=self.org.id,
            user_id=self.user.id,
            agent_slugs=[self.agent.slug],
            multiagentic_modality="grupal",
            requested_agent_slugs=[self.agent.slug, specialist.slug],
            run_at=future_local.strftime("%Y-%m-%dT%H:%M:%S"),
        )
        self.assertTrue(result.success)
        self.assertEqual(
            result.agent_slugs,
            [self.agent.slug, specialist.slug],
        )
        task = ScheduledConversationTask.objects.get(id=result.task_id)
        self.assertEqual(task.agent_slugs, [self.agent.slug, specialist.slug])
        self.assertEqual(task.multiagentic_modality, "grupal")

    @patch("api.messaging.tasks.run_scheduled_conversation_task.apply_async")
    def test_schedule_rejects_inaccessible_agent_slug(self, mock_apply):
        from api.ai_layers.tools.schedule_task import _schedule_task_impl

        future_local = (
            datetime.now(ZoneInfo("America/Guayaquil")) + timedelta(days=1)
        ).replace(hour=10, minute=0, second=0, microsecond=0)
        with self.assertRaises(ValueError) as ctx:
            _schedule_task_impl(
                title="Bad agents",
                instruction="1. Do work.",
                schedule_type="once",
                conversation_id=str(self.conversation.id),
                organization_id=self.org.id,
                user_id=self.user.id,
                agent_slugs=[self.agent.slug],
                multiagentic_modality="isolated",
                requested_agent_slugs=[self.agent.slug, "not-a-real-agent"],
                run_at=future_local.strftime("%Y-%m-%dT%H:%M:%S"),
            )
        self.assertIn("not found or not accessible", str(ctx.exception).lower())
        mock_apply.assert_not_called()

    @patch("api.messaging.tasks.run_scheduled_conversation_task.apply_async")
    def test_schedule_does_not_snapshot_tools(self, mock_apply):
        mock_apply.return_value = MagicMock(id="celery-caps-1")
        from api.ai_layers.tools.schedule_task import get_tool

        tool = get_tool(
            conversation_id=str(self.conversation.id),
            organization_id=self.org.id,
            user_id=self.user.id,
            agent_slugs=[self.agent.slug],
            multiagentic_modality="isolated",
            enabled_capabilities=[
                "create_speech",
                "list_voices",
                "send_email",
                "explore_web",
            ],
        )
        future_local = (
            datetime.now(ZoneInfo("America/Guayaquil")) + timedelta(days=3)
        ).replace(hour=9, minute=30, second=0, microsecond=0)
        result = tool["function"](
            title="Morning spoken brief",
            instruction="1. Draft a morning brief. 2. Generate spoken audio with create_speech.",
            schedule_type="once",
            run_at=future_local.strftime("%Y-%m-%dT%H:%M:%S"),
        )
        self.assertTrue(result.success)
        self.assertEqual(result.agent_slugs, [self.agent.slug])
        task = ScheduledConversationTask.objects.get(id=result.task_id)
        self.assertEqual(task.capabilities, [])
        self.assertNotIn("Optional tools allowlist", tool["description"])

    @patch("api.messaging.tasks.run_scheduled_conversation_task.apply_async")
    def test_schedule_weekly_and_cancel(self, mock_apply):
        mock_apply.return_value = MagicMock(id="celery-weekly-1")
        from api.ai_layers.tools.cancel_scheduled_task import _cancel_scheduled_task_impl
        from api.ai_layers.tools.list_scheduled_tasks import _list_scheduled_tasks_impl
        from api.ai_layers.tools.schedule_task import _schedule_task_impl

        result = _schedule_task_impl(
            title="Monday morning status",
            instruction=(
                "1. Generate a morning status docx. "
                "2. Email it to all organization members."
            ),
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
        self.assertEqual(listed.tasks[0]["title"], "Monday morning status")

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

    @patch("api.messaging.tasks.run_scheduled_conversation_task.apply_async")
    def test_schedule_requires_title(self, mock_apply):
        from api.ai_layers.tools.schedule_task import _schedule_task_impl

        with self.assertRaises(ValueError):
            _schedule_task_impl(
                title="  ",
                instruction="1. Do something.",
                schedule_type="recurring",
                conversation_id=str(self.conversation.id),
                organization_id=self.org.id,
                user_id=self.user.id,
                agent_slugs=[self.agent.slug],
                multiagentic_modality="isolated",
                recurrence="daily",
                time_of_day="10:00",
            )
        mock_apply.assert_not_called()

class ScheduleFirePathTests(TestCase):
    def setUp(self):
        self.llm = _seed_llm_and_currency()
        self.user = User.objects.create_user(
            username="fire", email="fire@test.com", password="x"
        )
        self.org = Organization.objects.create(
            name="Fire Org", owner=self.user, timezone="America/Guayaquil"
        )
        UserProfile.objects.filter(user=self.user).update(
            organization=self.org, name="Fire"
        )
        self.agent = Agent.objects.create(
            name="Fire Agent",
            salute="hi",
            act_as="help",
            user=self.user,
            organization=self.org,
            llm=self.llm,
            model_slug=self.llm.slug,
            model_provider="openai",
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
            title="Short status update",
            instruction_text="1. Write a short status update.",
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
        user_text = kwargs["user_inputs"][0]["text"]
        self.assertTrue(user_text.startswith("Executing task: Short status update"))
        self.assertIn("<!--", user_text)
        self.assertIn("SCHEDULED_TASK_EXECUTION", user_text)
        self.assertIn("one-off scheduled task", user_text)
        self.assertIn("Title: Short status update", user_text)
        self.assertIn("1. Write a short status update.", user_text)
        self.assertIn("Do NOT create, list, or cancel schedules", user_text)
        self.assertIn("each agent's pre_approved_tools", user_text)
        self.assertIn("-->", user_text)
        self.assertEqual(kwargs["tool_names"], [])
        self.assertNotIn("capabilities_override", kwargs)
        self.assertEqual(
            kwargs["user_message_metadata"],
            {
                "source": "scheduled_task",
                "scheduled_task_id": str(task.id),
                "scheduled_task_title": "Short status update",
                "scheduled_task_kind": "one-off",
                "schedule_type": ScheduledConversationTask.ScheduleType.ONCE,
                "scheduled_task_plan": "1. Write a short status update.",
            },
        )
        self.assertEqual(kwargs["agent_slugs"], [self.agent.slug])
        task.refresh_from_db()
        self.assertEqual(task.status, ScheduledConversationTask.Status.DONE)
        self.assertEqual(task.created_message_id, 42)

    @patch("api.ai_layers.tasks.conversation_agent_task")
    def test_fire_ignores_legacy_capabilities_field(self, mock_agent):
        mock_agent.return_value = {
            "status": "completed",
            "user_message_id": 43,
            "message_id": 100,
        }
        caps = [
            "create_speech",
            "list_voices",
            "generate_document_file",
            "explore_web",
            "schedule_task",
            "list_scheduled_tasks",
            "cancel_scheduled_task",
        ]
        task = self._make_pending(capabilities=caps)
        from api.messaging.tasks import run_scheduled_conversation_task

        run_scheduled_conversation_task(str(task.id))
        kwargs = mock_agent.call_args.kwargs
        self.assertEqual(kwargs["tool_names"], [])
        self.assertNotIn("capabilities_override", kwargs)
        self.assertNotIn("tools_constrained", kwargs["user_message_metadata"])
        self.assertEqual(kwargs["agent_slugs"], [self.agent.slug])

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
            title="Weekly Monday status",
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
        kwargs = mock_agent.call_args.kwargs
        user_text = kwargs["user_inputs"][0]["text"]
        self.assertIn("recurring scheduled task", user_text)
        self.assertEqual(kwargs["user_message_metadata"]["scheduled_task_kind"], "recurring")
        self.assertEqual(
            kwargs["user_message_metadata"]["scheduled_task_title"],
            "Weekly Monday status",
        )
        task.refresh_from_db()
        self.assertEqual(task.status, ScheduledConversationTask.Status.PENDING)
        self.assertGreater(task.next_run_at, timezone.now())
        mock_enqueue.assert_called_once()

class ScheduledCapabilityOverrideTests(TestCase):
    def setUp(self):
        self.llm = _seed_llm_and_currency()
        self.user = User.objects.create_user(
            username="cap_override", email="cap_override@test.com", password="x"
        )
        self.org = Organization.objects.create(
            name="Cap Org", owner=self.user, timezone="America/Guayaquil"
        )
        UserProfile.objects.filter(user=self.user).update(
            organization=self.org, name="Cap"
        )
        self.agent = Agent.objects.create(
            name="Cap Agent",
            salute="hi",
            act_as="help",
            user=self.user,
            organization=self.org,
            llm=self.llm,
            model_slug=self.llm.slug,
            model_provider="openai",
        )
        self.conversation = Conversation.objects.create(
            user=self.user,
            organization=self.org,
        )

    def test_empty_capabilities_means_unconstrained(self):
        from api.messaging.schedule_helpers import (
            effective_scheduled_task_tool_names,
            resolve_scheduled_task_capabilities,
            selectable_scheduled_task_tool_names,
        )

        task = ScheduledConversationTask(
            capabilities=[],
        )
        self.assertIsNone(resolve_scheduled_task_capabilities(task))
        effective = effective_scheduled_task_tool_names(task)
        self.assertEqual(effective, selectable_scheduled_task_tool_names())
        self.assertNotIn("schedule_task", effective)

    def test_resolve_strips_schedule_tools_from_snapshot(self):
        from api.messaging.schedule_helpers import resolve_scheduled_task_capabilities

        task = ScheduledConversationTask(
            capabilities=[
                "explore_web",
                "schedule_task",
                "list_scheduled_tasks",
                "cancel_scheduled_task",
                "send_email",
            ],
        )
        resolved = resolve_scheduled_task_capabilities(task)
        self.assertEqual(resolved, ["explore_web", "send_email"])

    def test_resolve_tools_schedule_task_has_no_capability_catalog(self):
        from api.ai_layers.tools import resolve_tools

        tools = resolve_tools(
            ["explore_web", "schedule_task", "create_speech"],
            conversation_id=str(self.conversation.id),
            organization_id=self.org.id,
            user_id=self.user.id,
            agent_slugs=[self.agent.slug],
            multiagentic_modality="isolated",
            enabled_capabilities=["explore_web", "schedule_task", "create_speech"],
        )
        by_name = {t["name"]: t for t in tools}
        self.assertIn("schedule_task", by_name)
        self.assertIn("list_voices", by_name)
        desc = by_name["schedule_task"]["description"]
        self.assertNotIn("Optional tools allowlist", desc)
        self.assertIn("pre_approved_tools", desc)

    @patch("api.notify.actions.notify_user")
    @patch("api.consumption.actions._check_org_subscription", return_value=(True, None))
    @patch("api.ai_layers.agent_loop.AgentLoop")
    @patch("api.ai_layers.tools.resolve_tools")
    def test_capabilities_override_blocks_auto_injection(
        self, mock_resolve_tools, mock_agent_loop, _billing, _notify
    ):
        from api.ai_layers.agent_loop import AgentLoopResult
        from api.ai_layers.tasks import conversation_agent_task

        captured: list[list[str]] = []

        def capture(names, **kwargs):
            captured.append(list(names))
            return []

        mock_resolve_tools.side_effect = capture
        mock_agent_loop.create.return_value.run.return_value = AgentLoopResult(
            output="ok",
            messages=[],
            iterations=1,
            tool_calls=[],
        )

        override = ["explore_web", "create_speech"]
        result = conversation_agent_task(
            conversation_id=str(self.conversation.id),
            user_inputs=[{"type": "input_text", "text": "hello"}],
            tool_names=list(override),
            agent_slugs=[self.agent.slug],
            user_id=self.user.id,
            capabilities_override=list(override),
        )
        self.assertEqual(result["status"], "completed")
        self.assertTrue(captured)
        self.assertEqual(set(captured[0]), set(override))
        self.assertNotIn("generate_document_file", captured[0])
        self.assertNotIn("send_email", captured[0])
        self.assertNotIn("schedule_task", captured[0])

    def test_cancelled_excluded_from_user_list_even_when_finished(self):
        from api.messaging.schedule_service import list_scheduled_tasks_for_user

        pending = ScheduledConversationTask.objects.create(
            conversation=self.conversation,
            organization=self.org,
            created_by=self.user,
            instruction_text="Pending",
            schedule_type=ScheduledConversationTask.ScheduleType.ONCE,
            timezone="America/Guayaquil",
            run_at=timezone.now() + timedelta(days=1),
            next_run_at=timezone.now() + timedelta(days=1),
            status=ScheduledConversationTask.Status.PENDING,
            agent_slugs=[self.agent.slug],
        )
        done = ScheduledConversationTask.objects.create(
            conversation=self.conversation,
            organization=self.org,
            created_by=self.user,
            instruction_text="Done",
            schedule_type=ScheduledConversationTask.ScheduleType.ONCE,
            timezone="America/Guayaquil",
            run_at=timezone.now() - timedelta(days=1),
            next_run_at=timezone.now() - timedelta(days=1),
            status=ScheduledConversationTask.Status.DONE,
            agent_slugs=[self.agent.slug],
        )
        cancelled = ScheduledConversationTask.objects.create(
            conversation=self.conversation,
            organization=self.org,
            created_by=self.user,
            instruction_text="Cancelled",
            schedule_type=ScheduledConversationTask.ScheduleType.ONCE,
            timezone="America/Guayaquil",
            run_at=timezone.now() + timedelta(days=2),
            next_run_at=timezone.now() + timedelta(days=2),
            status=ScheduledConversationTask.Status.CANCELLED,
            agent_slugs=[self.agent.slug],
        )

        active = list_scheduled_tasks_for_user(user_id=self.user.id, include_finished=False)
        active_ids = {t["id"] for t in active["tasks"]}
        self.assertEqual(active_ids, {str(pending.id)})
        self.assertNotIn(str(cancelled.id), active_ids)

        finished = list_scheduled_tasks_for_user(
            user_id=self.user.id, include_finished=True
        )
        finished_ids = {t["id"] for t in finished["tasks"]}
        self.assertEqual(finished_ids, {str(pending.id), str(done.id)})
        self.assertNotIn(str(cancelled.id), finished_ids)

class ScheduledTasksApiTests(TestCase):
    def setUp(self):
        from api.authenticate.models import Token
        from rest_framework.test import APIClient

        self.client = APIClient()
        self.llm = _seed_llm_and_currency()
        self.user = User.objects.create_user(
            username="api_sched", email="api_sched@test.com", password="x"
        )
        self.stranger = User.objects.create_user(
            username="stranger", email="stranger@test.com", password="x"
        )
        self.org = Organization.objects.create(
            name="API Org", owner=self.user, timezone="America/Guayaquil"
        )
        UserProfile.objects.filter(user=self.user).update(
            organization=self.org, name="API"
        )
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
        self.assertNotIn("available_tools", data)
        self.assertIn("agent_slugs", data["tasks"][0])

    def test_patch_capabilities_is_gone(self):
        response = self.client.patch(
            f"/v1/messaging/scheduled-tasks/{self.pending.id}/",
            data={"capabilities": ["explore_web", "send_email"]},
            format="json",
            **self._auth(self.token),
        )
        self.assertEqual(response.status_code, 410)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.capabilities, [])

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
