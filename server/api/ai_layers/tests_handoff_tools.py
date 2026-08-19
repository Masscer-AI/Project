"""Tests for list_agents, handoff_to_agent, and conversation handoff flow."""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from api.ai_layers.models import Agent, AgentKind, AgentSession, LanguageModel
from api.authenticate.models import Organization, UserProfile
from api.consumption.models import Currency
from api.messaging.models import Conversation, Message
from api.providers.models import AIProvider

def _seed_llm():
    Currency.objects.get_or_create(name="Compute Unit", defaults={"one_usd_is": 1000})
    provider = AIProvider.objects.create(name=f"OpenAI-ho-{LanguageModel.objects.count()}")
    return LanguageModel.objects.create(
        provider=provider,
        slug=f"gpt-ho-{LanguageModel.objects.count()}",
        name="GPT Handoff",
    )

class SuccessfulHandoffUserMessageTests(SimpleTestCase):
    def test_extracts_message_for_user_on_success(self):
        from api.ai_layers.agent_loop import successful_handoff_user_message

        record = {
            "tool_name": "handoff_to_agent",
            "arguments": {
                "agent_slug": "tax",
                "agent_instructions": "Need tax help",
                "message_for_user": "Passing you to Tax.",
            },
            "result": '{"success": true, "message": "ok", "to_agent_slug": "tax"}',
            "error": None,
        }
        self.assertEqual(
            successful_handoff_user_message(record),
            "Passing you to Tax.",
        )

    def test_ignores_failed_handoff(self):
        from api.ai_layers.agent_loop import successful_handoff_user_message

        record = {
            "tool_name": "handoff_to_agent",
            "arguments": {"message_for_user": "x"},
            "result": '{"success": false, "message": "nope"}',
            "error": None,
        }
        self.assertIsNone(successful_handoff_user_message(record))

    def test_ignores_other_tools(self):
        from api.ai_layers.agent_loop import successful_handoff_user_message

        record = {
            "tool_name": "list_agents",
            "arguments": {},
            "result": '{"agents": []}',
            "error": None,
        }
        self.assertIsNone(successful_handoff_user_message(record))

class BuildAgentLoopInputsHandoffTests(SimpleTestCase):
    def test_build_inputs_tags_other_agents_on_handoff_flag(self):
        from api.ai_layers.tasks import _build_agent_loop_inputs

        inputs = _build_agent_loop_inputs(
            prev_messages=[
                {
                    "type": "user",
                    "text": "Help",
                    "versions": [],
                    "attachments": [],
                },
                {
                    "type": "assistant",
                    "text": "Handing off",
                    "versions": [
                        {
                            "agent_slug": "legal-ho3",
                            "agent_name": "Legal",
                            "text": "Handing off",
                        }
                    ],
                    "attachments": [],
                },
            ],
            current_user_text="Continue",
            current_user_attachments=[],
            agent_slug="tax-ho3",
            multiagentic_modality="isolated",
            tag_other_agent_versions=True,
        )
        self.assertEqual(inputs[0]["role"], "user")
        self.assertEqual(inputs[1]["role"], "user")
        self.assertIn("Legal", inputs[1]["content"])
        self.assertEqual(inputs[2]["role"], "user")
        self.assertEqual(inputs[2]["content"], "Continue")

class ListAgentsToolTests(TestCase):
    def setUp(self):
        llm = _seed_llm()
        self.user = User.objects.create_user(username="ho-owner", password="x")
        self.org = Organization.objects.create(name="HO Org", owner=self.user)
        UserProfile.objects.get_or_create(user=self.user, defaults={"organization": self.org})
        self.agent_a = Agent.objects.create(
            name="Legal",
            slug="legal-ho",
            salute="hi",
            act_as="legal counsel persona",
            description="Handles contracts and legal questions",
            user=self.user,
            organization=self.org,
            llm=llm,
            agent_kind=AgentKind.CONVERSATIONAL_AGENT,
        )
        self.agent_b = Agent.objects.create(
            name="Tax",
            slug="tax-ho",
            salute="hi",
            act_as="tax specialist persona",
            description="SAT and tax compliance",
            user=self.user,
            organization=self.org,
            llm=llm,
            agent_kind=AgentKind.CONVERSATIONAL_AGENT,
        )
        self.platform = Agent.objects.create(
            name="Platform",
            slug="platform-ho",
            salute="hi",
            act_as="platform",
            description="Platform helper",
            organization=self.org,
            llm=llm,
            agent_kind=AgentKind.PLATFORM_ASSISTANT,
        )

    def test_lists_accessible_conversational_agents_with_description(self):
        from api.ai_layers.tools.list_agents import _list_agents_impl

        result = _list_agents_impl(
            user_id=self.user.id,
            current_agent_slug=self.agent_a.slug,
        )
        slugs = {a.slug for a in result.agents}
        self.assertIn(self.agent_b.slug, slugs)
        self.assertNotIn(self.agent_a.slug, slugs)
        self.assertNotIn(self.platform.slug, slugs)
        tax = next(a for a in result.agents if a.slug == self.agent_b.slug)
        self.assertEqual(tax.description, "SAT and tax compliance")

    def test_tools_registered(self):
        from api.ai_layers.tools import (
            DEPENDENT_TOOL_REQUIREMENTS,
            USER_REQUIRED_TOOL_NAMES,
            WIDGET_UNAVAILABLE_TOOL_NAMES,
            list_available_tools,
            list_registered_tools,
        )

        self.assertIn("handoff_to_agent", list_available_tools())
        self.assertIn("list_agents", list_registered_tools())
        self.assertNotIn("list_agents", list_available_tools())
        self.assertEqual(
            DEPENDENT_TOOL_REQUIREMENTS.get("list_agents"),
            ("handoff_to_agent",),
        )
        self.assertIn("list_agents", USER_REQUIRED_TOOL_NAMES)
        self.assertIn("handoff_to_agent", USER_REQUIRED_TOOL_NAMES)
        self.assertIn("list_agents", WIDGET_UNAVAILABLE_TOOL_NAMES)
        self.assertIn("handoff_to_agent", WIDGET_UNAVAILABLE_TOOL_NAMES)

class HandoffToAgentToolTests(TestCase):
    def setUp(self):
        llm = _seed_llm()
        self.user = User.objects.create_user(username="ho2-owner", password="x")
        self.org = Organization.objects.create(name="HO2 Org", owner=self.user)
        UserProfile.objects.get_or_create(user=self.user, defaults={"organization": self.org})
        self.agent_a = Agent.objects.create(
            name="Legal",
            slug="legal-ho2",
            salute="hi",
            act_as="legal",
            description="Legal",
            user=self.user,
            organization=self.org,
            llm=llm,
        )
        self.agent_b = Agent.objects.create(
            name="Tax",
            slug="tax-ho2",
            salute="hi",
            act_as="tax",
            description="Tax",
            user=self.user,
            organization=self.org,
            llm=llm,
        )

    def test_writes_handoff_request_on_success(self):
        from api.ai_layers.tools.handoff_to_agent import _handoff_to_agent_impl

        req: dict = {}
        result = _handoff_to_agent_impl(
            agent_slug=self.agent_b.slug,
            agent_instructions="Need SAT help on the invoice issue.",
            message_for_user="Handing this to Tax for the SAT question.",
            user_id=self.user.id,
            current_agent_slug=self.agent_a.slug,
            handoff_request=req,
        )
        self.assertTrue(result.success)
        self.assertTrue(req.get("requested"))
        self.assertEqual(req["to_agent_slug"], self.agent_b.slug)
        self.assertEqual(req["agent_instructions"], "Need SAT help on the invoice issue.")
        self.assertEqual(
            req["message_for_user"],
            "Handing this to Tax for the SAT question.",
        )
        self.assertNotIn("agent_instructions", req["message_for_user"])

    def test_rejects_self_handoff(self):
        from api.ai_layers.tools.handoff_to_agent import _handoff_to_agent_impl

        req: dict = {}
        result = _handoff_to_agent_impl(
            agent_slug=self.agent_a.slug,
            agent_instructions="x",
            message_for_user="y",
            user_id=self.user.id,
            current_agent_slug=self.agent_a.slug,
            handoff_request=req,
        )
        self.assertFalse(result.success)
        self.assertFalse(req.get("requested"))

    def test_rejects_embedded_channel(self):
        from api.ai_layers.tools.handoff_to_agent import _handoff_to_agent_impl

        req: dict = {}
        result = _handoff_to_agent_impl(
            agent_slug=self.agent_b.slug,
            agent_instructions="x",
            message_for_user="y",
            user_id=self.user.id,
            current_agent_slug=self.agent_a.slug,
            handoff_request=req,
            is_embedded_channel=True,
        )
        self.assertFalse(result.success)
        self.assertIn("WhatsApp", result.message)

    def test_rejects_second_handoff_same_turn(self):
        from api.ai_layers.tools.handoff_to_agent import _handoff_to_agent_impl

        req: dict = {"requested": True}
        result = _handoff_to_agent_impl(
            agent_slug=self.agent_b.slug,
            agent_instructions="x",
            message_for_user="y",
            user_id=self.user.id,
            current_agent_slug=self.agent_a.slug,
            handoff_request=req,
        )
        self.assertFalse(result.success)

class HandoffConversationTaskTests(TestCase):
    def setUp(self):
        llm = _seed_llm()
        self.user = User.objects.create_user(username="ho3-owner", password="x")
        self.org = Organization.objects.create(name="HO3 Org", owner=self.user)
        UserProfile.objects.get_or_create(user=self.user, defaults={"organization": self.org})
        self.agent_a = Agent.objects.create(
            name="Legal",
            slug="legal-ho3",
            salute="hi",
            act_as="legal",
            description="Legal",
            user=self.user,
            organization=self.org,
            llm=llm,
            pre_approved_tools=["handoff_to_agent"],
        )
        self.agent_b = Agent.objects.create(
            name="Tax",
            slug="tax-ho3",
            salute="hi",
            act_as="tax",
            description="Tax",
            user=self.user,
            organization=self.org,
            llm=llm,
            pre_approved_tools=["explore_web"],
        )
        self.conversation = Conversation.objects.create(
            user=self.user,
            organization=self.org,
            title="Handoff chat",
        )

    @patch("api.notify.actions.notify_user")
    @patch("api.consumption.actions._check_org_subscription", return_value=(True, None))
    @patch("api.ai_layers.tasks.conversation_agent_task.delay")
    @patch("api.ai_layers.agent_loop.AgentLoop")
    @patch("api.ai_layers.tools.resolve_tools")
    def test_handoff_saves_a_message_enqueues_b_without_new_user_row(
        self,
        mock_resolve_tools,
        mock_agent_loop,
        mock_delay,
        _billing,
        _notify,
    ):
        from api.ai_layers.agent_loop import AgentLoopResult
        from api.ai_layers.tasks import conversation_agent_task
        from api.messaging.schemas import metadata_payload_for_related_agents

        self.conversation.metadata = metadata_payload_for_related_agents(
            [self.agent_a.id]
        )
        self.conversation.save(update_fields=["metadata", "updated_at"])

        handoff_payload = {
            "requested": True,
            "to_agent_slug": self.agent_b.slug,
            "to_agent_name": self.agent_b.name,
            "to_agent_id": self.agent_b.id,
            "agent_instructions": "Private brief for Tax only.",
            "message_for_user": "I am handing this to Tax.",
            "from_agent_slug": self.agent_a.slug,
        }

        def fake_resolve(names, **kwargs):
            req = kwargs.get("handoff_request")
            if isinstance(req, dict):
                req.clear()
                req.update(handoff_payload)
            return []

        mock_resolve_tools.side_effect = fake_resolve
        mock_agent_loop.create.return_value.run.return_value = AgentLoopResult(
            output=handoff_payload["message_for_user"],
            messages=[],
            iterations=1,
            tool_calls=[
                {
                    "tool_name": "handoff_to_agent",
                    "arguments": {
                        "agent_slug": self.agent_b.slug,
                        "agent_instructions": handoff_payload["agent_instructions"],
                        "message_for_user": handoff_payload["message_for_user"],
                    },
                    "result": '{"success": true}',
                }
            ],
        )

        user_count_before = Message.objects.filter(
            conversation=self.conversation, type="user"
        ).count()

        result = conversation_agent_task(
            conversation_id=str(self.conversation.id),
            user_inputs=[{"type": "input_text", "text": "Help with SAT"}],
            tool_names=["handoff_to_agent"],
            agent_slugs=[self.agent_a.slug],
            user_id=self.user.id,
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result.get("handoff_to"), self.agent_b.slug)

        user_msgs = Message.objects.filter(
            conversation=self.conversation, type="user"
        )
        self.assertEqual(user_msgs.count(), user_count_before + 1)
        assistant_msgs = Message.objects.filter(
            conversation=self.conversation, type="assistant"
        )
        self.assertEqual(assistant_msgs.count(), 1)
        a_msg = assistant_msgs.get()
        self.assertEqual(a_msg.text, "I am handing this to Tax.")
        self.assertNotIn("Private brief", a_msg.text)
        self.assertEqual(a_msg.metadata.get("handoff", {}).get("to_slug"), self.agent_b.slug)

        sessions = AgentSession.objects.filter(conversation=self.conversation)
        self.assertEqual(sessions.count(), 1)
        session_a = sessions.get()
        self.assertIsNotNone(session_a.ended_at)
        self.assertEqual(session_a.assistant_message_id, a_msg.id)

        self.conversation.refresh_from_db()
        # Handoff must not rewrite the user's chat agent selection.
        related = (self.conversation.metadata or {}).get("related_agents") or []
        self.assertEqual(related, [{"id": self.agent_a.id}])

        mock_delay.assert_called_once()
        delay_kwargs = mock_delay.call_args.kwargs
        self.assertEqual(delay_kwargs["agent_slugs"], [self.agent_b.slug])
        self.assertTrue(delay_kwargs["skip_persist_user_message"])
        self.assertEqual(
            delay_kwargs["existing_user_message_id"],
            user_msgs.get().id,
        )
        self.assertEqual(delay_kwargs["tool_names"], [])
        self.assertNotIn("capabilities_override", delay_kwargs)
        meta = delay_kwargs["user_message_metadata"]
        self.assertEqual(meta["source"], "agent_handoff")
        self.assertEqual(meta["handoff_agent_instructions"], "Private brief for Tax only.")
        self.assertEqual(meta["handoff_from_slug"], self.agent_a.slug)

    @patch("api.notify.actions.notify_user")
    @patch("api.consumption.actions._check_org_subscription", return_value=(True, None))
    @patch("api.ai_layers.tasks.conversation_agent_task.delay")
    @patch("api.ai_layers.agent_loop.AgentLoop")
    @patch("api.ai_layers.tools.resolve_tools")
    def test_handoff_does_not_pass_capabilities_override_to_b(
        self,
        mock_resolve_tools,
        mock_agent_loop,
        mock_delay,
        _billing,
        _notify,
    ):
        """Handoff target B uses B's pre_approved_tools, not A's schedule fence."""
        from api.ai_layers.agent_loop import AgentLoopResult
        from api.ai_layers.tasks import conversation_agent_task

        handoff_payload = {
            "requested": True,
            "to_agent_slug": self.agent_b.slug,
            "to_agent_name": self.agent_b.name,
            "to_agent_id": self.agent_b.id,
            "agent_instructions": "Continue the scheduled plan.",
            "message_for_user": "Handing to Tax for the next steps.",
            "from_agent_slug": self.agent_a.slug,
        }

        def fake_resolve(names, **kwargs):
            req = kwargs.get("handoff_request")
            if isinstance(req, dict):
                req.clear()
                req.update(handoff_payload)
            return []

        mock_resolve_tools.side_effect = fake_resolve
        mock_agent_loop.create.return_value.run.return_value = AgentLoopResult(
            output=handoff_payload["message_for_user"],
            messages=[],
            iterations=1,
            tool_calls=[],
        )

        override = ["explore_web", "send_email", "handoff_to_agent", "list_agents"]
        result = conversation_agent_task(
            conversation_id=str(self.conversation.id),
            user_inputs=[{"type": "input_text", "text": "Scheduled work"}],
            tool_names=["explore_web"],
            agent_slugs=[self.agent_a.slug],
            user_id=self.user.id,
            capabilities_override=override,
            user_message_metadata={
                "source": "scheduled_task",
                "scheduled_task_plan": "1. Research. 2. Email.",
            },
        )
        self.assertEqual(result["status"], "completed")
        mock_delay.assert_called_once()
        delay_kwargs = mock_delay.call_args.kwargs
        self.assertEqual(delay_kwargs["tool_names"], [])
        self.assertNotIn("capabilities_override", delay_kwargs)
        self.assertEqual(delay_kwargs["agent_slugs"], [self.agent_b.slug])

    @patch("api.notify.actions.notify_user")
    @patch("api.consumption.actions._check_org_subscription", return_value=(True, None))
    @patch("api.ai_layers.agent_loop.AgentLoop")
    @patch("api.ai_layers.tools.resolve_tools")
    def test_handoff_continuation_injects_instructions_and_skips_new_user_message(
        self,
        mock_resolve_tools,
        mock_agent_loop,
        _billing,
        _notify,
    ):
        from api.ai_layers.agent_loop import AgentLoopResult
        from api.ai_layers.tasks import conversation_agent_task

        user_msg = Message.objects.create(
            conversation=self.conversation,
            type="user",
            text="Help with SAT",
        )
        Message.objects.create(
            conversation=self.conversation,
            type="assistant",
            text="I am handing this to Tax.",
            versions=[
                {
                    "agent_slug": self.agent_a.slug,
                    "agent_name": self.agent_a.name,
                    "type": "assistant",
                    "text": "I am handing this to Tax.",
                }
            ],
            metadata={"handoff": {"to_slug": self.agent_b.slug}},
        )

        captured_instructions: list[str] = []
        captured_inputs: list[list] = []

        def capture_create(**kwargs):
            captured_instructions.append(kwargs.get("instructions") or "")
            loop = mock_agent_loop.create.return_value

            def run(inputs):
                captured_inputs.append(inputs)
                return AgentLoopResult(
                    output="Tax answer here.",
                    messages=[],
                    iterations=1,
                    tool_calls=[],
                )

            loop.run.side_effect = run
            return loop

        mock_agent_loop.create.side_effect = capture_create
        mock_resolve_tools.return_value = []

        user_count_before = Message.objects.filter(
            conversation=self.conversation, type="user"
        ).count()

        result = conversation_agent_task(
            conversation_id=str(self.conversation.id),
            user_inputs=[{"type": "input_text", "text": "Help with SAT"}],
            tool_names=["explore_web"],
            agent_slugs=[self.agent_b.slug],
            user_id=self.user.id,
            skip_persist_user_message=True,
            existing_user_message_id=user_msg.id,
            user_message_metadata={
                "source": "agent_handoff",
                "handoff_from_slug": self.agent_a.slug,
                "handoff_from_name": self.agent_a.name,
                "handoff_agent_instructions": "Private brief for Tax only.",
            },
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(
            Message.objects.filter(
                conversation=self.conversation, type="user"
            ).count(),
            user_count_before,
        )
        self.assertEqual(
            Message.objects.filter(
                conversation=self.conversation, type="assistant"
            ).count(),
            2,
        )
        b_msg = (
            Message.objects.filter(
                conversation=self.conversation, type="assistant"
            )
            .order_by("-id")
            .first()
        )
        self.assertEqual(b_msg.text, "Tax answer here.")
        self.assertNotIn("Private brief", b_msg.text)

        self.assertTrue(captured_instructions)
        self.assertIn("AGENT HANDOFF", captured_instructions[0])
        self.assertIn("Private brief for Tax only.", captured_instructions[0])

        self.assertTrue(captured_inputs)
        roles_and_content = [
            (m.get("role"), m.get("content", "")) for m in captured_inputs[0]
        ]
        tagged = [
            c
            for r, c in roles_and_content
            if r == "user" and "I am handing this to Tax." in c and "Legal" in c
        ]
        self.assertTrue(tagged)
        own_assistant = [
            c
            for r, c in roles_and_content
            if r == "assistant" and "I am handing this to Tax." in c
        ]
        self.assertFalse(own_assistant)
