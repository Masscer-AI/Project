from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from api.ai_layers.models import Agent
from api.authenticate.models import Organization, UserProfile
from api.messaging.models import Conversation, Message
from api.whatsapp.models import WSNumber
from api.whatsapp.template_registry import (
    TASK_COMPLETED,
    get_template,
    list_enabled_templates,
    template_summary,
)
from api.whatsapp.template_send import (
    TemplateVariables,
    build_template_components,
    send_ws_template_to_member,
)


class WhatsAppSendTemplateMessageGraphTests(SimpleTestCase):
    @patch("api.whatsapp.actions.requests.post")
    @patch("api.whatsapp.actions._graph_token", return_value="token")
    def test_send_template_message_payload(self, _token, mock_post):
        from api.whatsapp.actions import send_template_message

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "messages": [{"id": "wamid.graph.1"}]
        }
        wamid = send_template_message(
            "pnid-1",
            "525512345678",
            template_name="task_completed",
            language_code="en",
            components=[
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": "Task"},
                        {"type": "text", "text": "Summary"},
                    ],
                }
            ],
        )
        self.assertEqual(wamid, "wamid.graph.1")
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["type"], "template")
        self.assertEqual(payload["template"]["name"], "task_completed")
        self.assertEqual(payload["template"]["language"]["code"], "en")
        self.assertEqual(payload["to"], "525512345678")

    @patch("api.whatsapp.actions.requests.post")
    @patch("api.whatsapp.actions._graph_token", return_value="token")
    def test_send_template_message_raises_meta_error(self, _token, mock_post):
        from api.whatsapp.actions import send_template_message

        mock_post.return_value.status_code = 400
        mock_post.return_value.json.return_value = {
            "error": {"message": "Template name does not exist in the translation"}
        }
        mock_post.return_value.text = "bad"
        with self.assertRaises(Exception) as ctx:
            send_template_message(
                "pnid-1",
                "525512345678",
                template_name="missing",
                language_code="en",
            )
        self.assertIn("Template name does not exist", str(ctx.exception))


class WhatsAppTemplateRegistryTests(SimpleTestCase):
    def test_task_completed_registered(self):
        tpl = get_template("task_completed_en")
        self.assertIsNotNone(tpl)
        self.assertEqual(tpl.meta_name, "task_completed")
        self.assertEqual(tpl.language_code, "en")
        self.assertEqual(tpl.body_variable_count, 2)
        self.assertEqual(tpl.button_variable_count, 1)
        self.assertTrue(tpl.buttons[0].use_source_conversation_id)

    def test_list_enabled_includes_task_completed(self):
        ids = {t.id for t in list_enabled_templates()}
        self.assertIn(TASK_COMPLETED.id, ids)

    def test_unknown_template_returns_none(self):
        self.assertIsNone(get_template("does_not_exist"))

    def test_build_components_for_task_completed(self):
        components = build_template_components(
            TASK_COMPLETED,
            TemplateVariables(
                body=["Weekly summary", "300 conversations started"],
                buttons=None,
            ),
            source_conversation_id="11111111-1111-1111-1111-111111111111",
        )
        self.assertEqual(components[0]["type"], "body")
        self.assertEqual(len(components[0]["parameters"]), 2)
        self.assertEqual(components[1]["type"], "button")
        self.assertEqual(components[1]["sub_type"], "url")
        self.assertEqual(components[1]["index"], "0")
        self.assertEqual(
            components[1]["parameters"][0]["text"],
            "11111111-1111-1111-1111-111111111111",
        )

    def test_build_components_rejects_wrong_body_count(self):
        with self.assertRaises(ValueError) as ctx:
            build_template_components(
                TASK_COMPLETED,
                TemplateVariables(body=["only one"]),
                source_conversation_id="abc",
            )
        self.assertIn("expects 2 body", str(ctx.exception))

    def test_template_summary_shape(self):
        summary = template_summary(TASK_COMPLETED)
        self.assertEqual(summary["template_id"], "task_completed_en")
        self.assertEqual(summary["body_variable_count"], 2)


class WhatsAppTemplateSendTests(TestCase):
    def setUp(self):
        from api.ai_layers.models import LanguageModel
        from api.consumption.models import Currency
        from api.providers.models import AIProvider

        Currency.objects.get_or_create(
            name="Compute Unit", defaults={"one_usd_is": 1000}
        )
        provider = AIProvider.objects.create(name="OpenAI-wa-tpl")
        self.llm = LanguageModel.objects.create(
            provider=provider, slug="gpt-wa-tpl", name="GPT WA Tpl"
        )

        self.owner = User.objects.create_user(
            username="wa_tpl_owner",
            email="owner@example.com",
            password="x",
        )
        self.member = User.objects.create_user(
            username="wa_tpl_member",
            email="member@example.com",
            password="x",
        )
        self.org = Organization.objects.create(name="WA Tpl Org", owner=self.owner)
        owner_profile = UserProfile.objects.get(user=self.owner)
        owner_profile.organization = self.org
        owner_profile.save(update_fields=["organization", "updated_at"])

        member_profile = UserProfile.objects.get(user=self.member)
        member_profile.organization = self.org
        member_profile.is_active = True
        member_profile.phone_numbers = [
            {
                "country_code": "52",
                "number": "5512345678",
                "is_default": True,
            }
        ]
        member_profile.save()

        self.agent = Agent.objects.create(
            name="Org WA Agent",
            salute="hi",
            organization=self.org,
            user=self.owner,
            llm=self.llm,
            model_slug=self.llm.slug,
        )
        self.ws = WSNumber.objects.create(
            organization=self.org,
            user=self.owner,
            agent=self.agent,
            name="Support Line",
            number="525500000000",
            platform_id="pnid-tpl",
            verified=True,
        )
        self.source_conversation = Conversation.objects.create(
            user=self.owner,
            organization=self.org,
            title="Source web chat",
        )
        self.target_phone = "525512345678"
        self.wa_conversation = Conversation.objects.create(
            user=None,
            organization=self.org,
            ws_number=self.ws,
            whatsapp_user_number=self.target_phone,
            status="active",
            title="WA visitor thread",
        )

    @patch("api.whatsapp.template_send.send_template_message")
    def test_send_success_persists_on_delivery_conversation(self, mock_send):
        mock_send.return_value = "wamid.template.1"
        result = send_ws_template_to_member(
            actor_user_id=self.owner.id,
            organization_id=self.org.id,
            sender_id=self.ws.id,
            target_user_id=self.member.id,
            target_phone_number=self.target_phone,
            template_id="task_completed_en",
            template_variables={
                "body": ["Finish weekly report", "All good this week"],
            },
            source_conversation_id=str(self.source_conversation.id),
        )
        self.assertTrue(result.sent)
        self.assertEqual(result.wamid, "wamid.template.1")
        self.assertEqual(
            result.delivery_conversation_id, str(self.wa_conversation.id)
        )

        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs["template_name"], "task_completed")
        self.assertEqual(kwargs["language_code"], "en")
        components = kwargs["components"]
        self.assertEqual(components[0]["type"], "body")
        self.assertEqual(
            components[1]["parameters"][0]["text"],
            str(self.source_conversation.id),
        )

        msg = Message.objects.filter(conversation=self.wa_conversation).latest(
            "created_at"
        )
        self.assertEqual(msg.metadata.get("whatsapp_wamid"), "wamid.template.1")
        self.assertEqual(msg.metadata.get("whatsapp_template_id"), "task_completed_en")
        self.assertEqual(
            msg.metadata.get("source_conversation_id"),
            str(self.source_conversation.id),
        )
        # Must not create messages on the web source conversation.
        self.assertFalse(
            Message.objects.filter(conversation=self.source_conversation).exists()
        )

    @patch("api.whatsapp.template_send.send_template_message")
    def test_reopens_inactive_thread_when_prior_contact_exists(self, mock_send):
        mock_send.return_value = "wamid.reopen"
        self.wa_conversation.status = "inactive"
        self.wa_conversation.save(update_fields=["status", "updated_at"])

        result = send_ws_template_to_member(
            actor_user_id=self.owner.id,
            organization_id=self.org.id,
            sender_id=self.ws.id,
            target_user_id=self.member.id,
            target_phone_number=self.target_phone,
            template_id="task_completed_en",
            template_variables={
                "body": ["Task", "Summary"],
            },
            source_conversation_id=str(self.source_conversation.id),
        )
        self.assertTrue(result.sent)
        self.assertNotEqual(
            result.delivery_conversation_id, str(self.wa_conversation.id)
        )
        new_conv = Conversation.objects.get(id=result.delivery_conversation_id)
        self.assertEqual(new_conv.status, "active")
        self.assertEqual(new_conv.whatsapp_user_number, self.target_phone)

    def test_rejects_unknown_template(self):
        with self.assertRaises(ValueError) as ctx:
            send_ws_template_to_member(
                actor_user_id=self.owner.id,
                organization_id=self.org.id,
                sender_id=self.ws.id,
                target_user_id=self.member.id,
                target_phone_number=self.target_phone,
                template_id="not_registered",
                template_variables={"body": ["a", "b"]},
                source_conversation_id=str(self.source_conversation.id),
            )
        self.assertIn("Unknown or disabled", str(ctx.exception))

    def test_rejects_unregistered_phone(self):
        with self.assertRaises(ValueError) as ctx:
            send_ws_template_to_member(
                actor_user_id=self.owner.id,
                organization_id=self.org.id,
                sender_id=self.ws.id,
                target_user_id=self.member.id,
                target_phone_number="525599999999",
                template_id="task_completed_en",
                template_variables={"body": ["a", "b"]},
                source_conversation_id=str(self.source_conversation.id),
            )
        self.assertIn("not registered", str(ctx.exception))

    def test_rejects_no_prior_contact(self):
        member2 = User.objects.create_user(
            username="wa_tpl_member2",
            email="member2@example.com",
            password="x",
        )
        profile = UserProfile.objects.get(user=member2)
        profile.organization = self.org
        profile.phone_numbers = [
            {"country_code": "52", "number": "5599998888", "is_default": True}
        ]
        profile.save()

        with self.assertRaises(ValueError) as ctx:
            send_ws_template_to_member(
                actor_user_id=self.owner.id,
                organization_id=self.org.id,
                sender_id=self.ws.id,
                target_user_id=member2.id,
                target_phone_number="525599998888",
                template_id="task_completed_en",
                template_variables={"body": ["a", "b"]},
                source_conversation_id=str(self.source_conversation.id),
            )
        self.assertIn("never contacted", str(ctx.exception))

    def test_rejects_cross_org_sender(self):
        other_owner = User.objects.create_user(
            username="other_org_owner", email="o@example.com", password="x"
        )
        other_org = Organization.objects.create(name="Other", owner=other_owner)
        other_agent = Agent.objects.create(
            name="Other Agent",
            salute="hi",
            organization=other_org,
            user=other_owner,
            llm=self.llm,
            model_slug=self.llm.slug,
        )
        other_ws = WSNumber.objects.create(
            organization=other_org,
            agent=other_agent,
            number="525511111111",
            platform_id="pnid-other",
        )
        with self.assertRaises(ValueError) as ctx:
            send_ws_template_to_member(
                actor_user_id=self.owner.id,
                organization_id=self.org.id,
                sender_id=other_ws.id,
                target_user_id=self.member.id,
                target_phone_number=self.target_phone,
                template_id="task_completed_en",
                template_variables={"body": ["a", "b"]},
                source_conversation_id=str(self.source_conversation.id),
            )
        self.assertIn("does not belong", str(ctx.exception))

    @patch("api.whatsapp.template_send.send_template_message")
    def test_surfaces_graph_failure(self, mock_send):
        mock_send.side_effect = Exception("Template paused")
        with self.assertRaises(ValueError) as ctx:
            send_ws_template_to_member(
                actor_user_id=self.owner.id,
                organization_id=self.org.id,
                sender_id=self.ws.id,
                target_user_id=self.member.id,
                target_phone_number=self.target_phone,
                template_id="task_completed_en",
                template_variables={"body": ["a", "b"]},
                source_conversation_id=str(self.source_conversation.id),
            )
        self.assertIn("Failed to send WhatsApp template", str(ctx.exception))


class WhatsAppTemplateToolsTests(TestCase):
    def setUp(self):
        from api.ai_layers.models import LanguageModel
        from api.consumption.models import Currency
        from api.providers.models import AIProvider

        Currency.objects.get_or_create(
            name="Compute Unit", defaults={"one_usd_is": 1000}
        )
        provider = AIProvider.objects.create(name="OpenAI-wa-tools")
        llm = LanguageModel.objects.create(
            provider=provider, slug="gpt-wa-tools", name="GPT WA Tools"
        )

        self.owner = User.objects.create_user(
            username="wa_tools_owner",
            email="tools-owner@example.com",
            password="x",
        )
        self.org = Organization.objects.create(name="Tools Org", owner=self.owner)
        profile = UserProfile.objects.get(user=self.owner)
        profile.organization = self.org
        profile.phone_numbers = [
            {"country_code": "1", "number": "5550001111", "is_default": True}
        ]
        profile.save()
        self.agent = Agent.objects.create(
            name="Tools Agent",
            salute="hi",
            organization=self.org,
            user=self.owner,
            llm=llm,
            model_slug=llm.slug,
        )
        self.ws = WSNumber.objects.create(
            organization=self.org,
            agent=self.agent,
            number="15550002222",
            platform_id="pnid-tools",
            name="Main",
        )

    def test_tools_registered(self):
        from api.ai_layers.tools import list_available_tools

        names = list_available_tools()
        self.assertIn("list_accessible_whatsapp_senders", names)
        self.assertIn("list_whatsapp_templates", names)
        self.assertIn("send_ws_template_message", names)

    def test_send_tool_nested_schema_has_no_ref_siblings(self):
        from api.ai_layers.tools.send_ws_template_message import (
            SendWsTemplateMessageParams,
        )

        schema = SendWsTemplateMessageParams.model_json_schema()
        template_variables = schema["properties"]["template_variables"]
        self.assertEqual(
            template_variables,
            {"$ref": "#/$defs/TemplateVariables"},
        )

    def test_list_templates_tool(self):
        from api.ai_layers.tools.list_whatsapp_templates import get_tool

        tool = get_tool()
        result = tool["function"]()
        ids = {t.template_id for t in result.templates}
        self.assertIn("task_completed_en", ids)

    def test_list_senders_tool(self):
        from api.ai_layers.tools.list_accessible_whatsapp_senders import get_tool

        tool = get_tool(organization_id=self.org.id, user_id=self.owner.id)
        result = tool["function"]()
        self.assertEqual(len(result.senders), 1)
        self.assertEqual(result.senders[0].sender_id, self.ws.id)
        self.assertEqual(result.senders[0].agent_slug, self.agent.slug)

    def test_list_senders_requires_authenticated_int_user(self):
        from api.ai_layers.tools.list_accessible_whatsapp_senders import get_tool

        with self.assertRaises(ValueError):
            get_tool(organization_id=self.org.id, user_id="whatsapp:uuid")

    def test_send_tool_requires_web_user(self):
        from api.ai_layers.tools.send_ws_template_message import get_tool

        with self.assertRaises(ValueError):
            get_tool(
                conversation_id="11111111-1111-1111-1111-111111111111",
                user_id="whatsapp:abc",
                organization_id=self.org.id,
            )

    def test_not_in_whatsapp_visitor_capabilities(self):
        from api.whatsapp.capability_tools import WHATSAPP_ALLOWED_CAPABILITY_TOOLS

        self.assertNotIn(
            "send_ws_template_message", WHATSAPP_ALLOWED_CAPABILITY_TOOLS
        )
        self.assertNotIn(
            "list_accessible_whatsapp_senders", WHATSAPP_ALLOWED_CAPABILITY_TOOLS
        )
        self.assertNotIn(
            "list_whatsapp_templates", WHATSAPP_ALLOWED_CAPABILITY_TOOLS
        )

    def test_list_organization_members_includes_phone_numbers(self):
        from api.ai_layers.tools.list_organization_members import (
            _list_organization_members_impl,
        )

        result = _list_organization_members_impl(self.org.id, self.owner.id)
        owner = next(m for m in result.members if m.user_id == self.owner.id)
        self.assertEqual(len(owner.phone_numbers), 1)
        self.assertEqual(owner.phone_numbers[0].country_code, "1")
        self.assertEqual(owner.phone_numbers[0].number, "5550001111")

    def test_mcp_preset_includes_whatsapp_group(self):
        from api.ai_layers.mcp_access import mcp_tool_preset_groups

        groups = {g["group"]: g["items"] for g in mcp_tool_preset_groups()}
        self.assertIn("whatsapp", groups)
        self.assertIn("send_ws_template_message", groups["whatsapp"])
