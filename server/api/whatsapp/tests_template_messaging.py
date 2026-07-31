from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from api.ai_layers.models import Agent
from api.authenticate.models import Organization, UserProfile
from api.messaging.models import Conversation, Message
from api.whatsapp.conversations import (
    create_whatsapp_conversation,
    get_or_create_whatsapp_conversation,
)
from api.whatsapp.models import WSContact, WSNumber
from api.whatsapp.template_registry import (
    APROBACION_PENDIENTE,
    APPROVAL_PENDING,
    SOLICITUD_COMPLETADA,
    TASK_COMPLETED,
    get_template,
    list_enabled_templates,
    template_summary,
)
from api.whatsapp.template_send import (
    TemplateVariables,
    build_template_components,
    format_template_delivery_message,
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


class WhatsAppTemplateDeliveryMessageFormatTests(SimpleTestCase):
    def test_format_matches_dashboard_markdown(self):
        text = format_template_delivery_message(
            APPROVAL_PENDING,
            TemplateVariables(
                body=[
                    "Send test WhatsApp message",
                    "I will send a test message when you grant approval.",
                ]
            ),
            source_conversation_id="11111111-1111-4111-8111-111111111111",
        )
        self.assertEqual(
            text,
            (
                "---\n"
                "[Send from another conversation](/chat?conversation="
                "11111111-1111-4111-8111-111111111111)\n"
                "\n"
                "### Send test WhatsApp message\n"
                "\n"
                "I will send a test message when you grant approval.\n"
                "---"
            ),
        )


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

    def test_solicitud_completada_spanish_registered(self):
        tpl = get_template("solicitud_completada_es")
        self.assertIsNotNone(tpl)
        self.assertEqual(tpl.meta_name, "solicitud_completada")
        self.assertEqual(tpl.language_code, "es")
        self.assertEqual(tpl.body_variable_count, 2)
        self.assertEqual(tpl.button_variable_count, 1)
        self.assertTrue(tpl.buttons[0].use_source_conversation_id)

        ids = {t.id for t in list_enabled_templates()}
        self.assertIn(SOLICITUD_COMPLETADA.id, ids)

    def test_aprobacion_pendiente_spanish_registered(self):
        tpl = get_template("aprobacion_pendiente_es")
        self.assertIsNotNone(tpl)
        self.assertEqual(tpl.meta_name, "aprobacion_pendiente")
        self.assertEqual(tpl.language_code, "es")
        self.assertEqual(tpl.body_variable_count, 2)
        self.assertEqual(tpl.button_variable_count, 0)
        self.assertEqual(tpl.buttons, ())

        ids = {t.id for t in list_enabled_templates()}
        self.assertIn(APROBACION_PENDIENTE.id, ids)

    def test_approval_pending_english_registered(self):
        tpl = get_template("approval_pending_en")
        self.assertIsNotNone(tpl)
        self.assertEqual(tpl.meta_name, "approval_pending")
        self.assertEqual(tpl.language_code, "en")
        self.assertEqual(tpl.body_variable_count, 2)
        self.assertEqual(tpl.button_variable_count, 0)
        self.assertEqual(tpl.buttons, ())

        ids = {t.id for t in list_enabled_templates()}
        self.assertIn(APPROVAL_PENDING.id, ids)

    def test_build_components_for_aprobacion_pendiente(self):
        components = build_template_components(
            APROBACION_PENDIENTE,
            TemplateVariables(
                body=[
                    "indexación del contrato marco Q3",
                    (
                        "Procesar el PDF, indexarlo en la base de conocimiento "
                        "y avisar al equipo cuando esté listo."
                    ),
                ],
            ),
            source_conversation_id="11111111-1111-1111-1111-111111111111",
        )
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0]["type"], "body")
        self.assertEqual(len(components[0]["parameters"]), 2)

    def test_build_components_for_approval_pending(self):
        components = build_template_components(
            APPROVAL_PENDING,
            TemplateVariables(
                body=[
                    "ACME quote review",
                    (
                        "Send the $45,000 quote to the vendor and update "
                        "the status in Masscer."
                    ),
                ],
            ),
            source_conversation_id="11111111-1111-1111-1111-111111111111",
        )
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0]["type"], "body")
        self.assertEqual(len(components[0]["parameters"]), 2)

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


class WhatsAppContactBridgeTests(TestCase):
    def setUp(self):
        from api.ai_layers.models import LanguageModel
        from api.consumption.models import Currency
        from api.providers.models import AIProvider

        Currency.objects.get_or_create(
            name="Compute Unit", defaults={"one_usd_is": 1000}
        )
        provider = AIProvider.objects.create(name="OpenAI-wa-contact")
        llm = LanguageModel.objects.create(
            provider=provider, slug="gpt-wa-contact", name="GPT WA Contact"
        )
        self.owner = User.objects.create_user(
            username="wa_contact_owner",
            email="contact-owner@example.com",
            password="x",
        )
        self.org = Organization.objects.create(name="Contact Org", owner=self.owner)
        profile = UserProfile.objects.get(user=self.owner)
        profile.organization = self.org
        profile.save(update_fields=["organization", "updated_at"])
        self.agent = Agent.objects.create(
            name="Contact Agent",
            salute="hi",
            organization=self.org,
            user=self.owner,
            llm=llm,
            model_slug=llm.slug,
        )
        self.ws = WSNumber.objects.create(
            organization=self.org,
            agent=self.agent,
            number="525500000001",
            platform_id="pnid-contact",
        )

    def test_get_or_create_conversation_creates_contact(self):
        conv = get_or_create_whatsapp_conversation(self.ws, "525511122233")
        self.assertIsNotNone(conv.ws_contact_id)
        contact = conv.ws_contact
        self.assertEqual(contact.number, "525511122233")
        self.assertIsNone(contact.user_id)

        again = get_or_create_whatsapp_conversation(self.ws, "525511122233")
        self.assertEqual(again.id, conv.id)
        self.assertEqual(again.ws_contact_id, contact.id)

    def test_clear_reuses_same_contact(self):
        first = create_whatsapp_conversation(self.ws, "525544455566")
        first.status = "inactive"
        first.save(update_fields=["status", "updated_at"])
        second = create_whatsapp_conversation(self.ws, "525544455566")
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(first.ws_contact_id, second.ws_contact_id)

    def test_same_user_can_link_two_contacts(self):
        member = User.objects.create_user(
            username="multi_phone", email="mp@example.com", password="x"
        )
        profile = UserProfile.objects.get(user=member)
        profile.organization = self.org
        profile.is_active = True
        profile.save()

        c1 = WSContact.objects.create(ws_number=self.ws, number="525511111111")
        c2 = WSContact.objects.create(ws_number=self.ws, number="525522222222")
        c1.user = member
        c1.save(update_fields=["user", "updated_at"])
        c2.user = member
        c2.save(update_fields=["user", "updated_at"])
        self.assertEqual(
            WSContact.objects.filter(ws_number=self.ws, user=member).count(), 2
        )


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
        self.contact = WSContact.objects.create(
            ws_number=self.ws,
            number=self.target_phone,
            user=self.member,
        )
        self.wa_conversation = Conversation.objects.create(
            user=None,
            organization=self.org,
            ws_number=self.ws,
            ws_contact=self.contact,
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
            agent_id=self.agent.id,
            sender_id=self.ws.id,
            ws_contact_id=self.contact.id,
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
        self.assertEqual(result.ws_contact_id, self.contact.id)

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
        self.assertEqual(msg.metadata.get("ws_contact_id"), self.contact.id)
        self.assertEqual(
            msg.metadata.get("source_conversation_id"),
            str(self.source_conversation.id),
        )
        self.assertIn("---", msg.text)
        self.assertIn(
            f"[Send from another conversation](/chat?conversation={self.source_conversation.id})",
            msg.text,
        )
        self.assertIn("### Finish weekly report", msg.text)
        self.assertIn("All good this week", msg.text)
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
            agent_id=self.agent.id,
            sender_id=self.ws.id,
            ws_contact_id=self.contact.id,
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
        self.assertEqual(new_conv.ws_contact_id, self.contact.id)

    @patch("api.whatsapp.template_send.send_template_message")
    def test_multi_phone_user_uses_chosen_contact(self, mock_send):
        mock_send.return_value = "wamid.phone2"
        other_phone = "525598765432"
        contact2 = WSContact.objects.create(
            ws_number=self.ws,
            number=other_phone,
            user=self.member,
        )
        Conversation.objects.create(
            user=None,
            organization=self.org,
            ws_number=self.ws,
            ws_contact=contact2,
            whatsapp_user_number=other_phone,
            status="active",
        )
        result = send_ws_template_to_member(
            actor_user_id=self.owner.id,
            organization_id=self.org.id,
            agent_id=self.agent.id,
            sender_id=self.ws.id,
            ws_contact_id=contact2.id,
            template_id="task_completed_en",
            template_variables={"body": ["a", "b"]},
            source_conversation_id=str(self.source_conversation.id),
        )
        self.assertEqual(result.target_phone, other_phone)
        self.assertEqual(mock_send.call_args.args[1], other_phone)

    def test_rejects_unknown_template(self):
        with self.assertRaises(ValueError) as ctx:
            send_ws_template_to_member(
                actor_user_id=self.owner.id,
                organization_id=self.org.id,
                agent_id=self.agent.id,
                sender_id=self.ws.id,
                ws_contact_id=self.contact.id,
                template_id="not_registered",
                template_variables={"body": ["a", "b"]},
                source_conversation_id=str(self.source_conversation.id),
            )
        self.assertIn("Unknown or disabled", str(ctx.exception))

    def test_rejects_unlinked_contact(self):
        self.contact.user = None
        self.contact.save(update_fields=["user", "updated_at"])
        with self.assertRaises(ValueError) as ctx:
            send_ws_template_to_member(
                actor_user_id=self.owner.id,
                organization_id=self.org.id,
                agent_id=self.agent.id,
                sender_id=self.ws.id,
                ws_contact_id=self.contact.id,
                template_id="task_completed_en",
                template_variables={"body": ["a", "b"]},
                source_conversation_id=str(self.source_conversation.id),
            )
        self.assertIn("not verified", str(ctx.exception))

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
                agent_id=self.agent.id,
                sender_id=other_ws.id,
                ws_contact_id=self.contact.id,
                template_id="task_completed_en",
                template_variables={"body": ["a", "b"]},
                source_conversation_id=str(self.source_conversation.id),
            )
        self.assertIn("does not belong", str(ctx.exception))

    def test_rejects_sender_assigned_to_other_agent(self):
        other_agent = Agent.objects.create(
            name="Sibling Agent",
            salute="hi",
            organization=self.org,
            user=self.owner,
            llm=self.llm,
            model_slug=self.llm.slug,
        )
        with self.assertRaises(ValueError) as ctx:
            send_ws_template_to_member(
                actor_user_id=self.owner.id,
                organization_id=self.org.id,
                agent_id=other_agent.id,
                sender_id=self.ws.id,
                ws_contact_id=self.contact.id,
                template_id="task_completed_en",
                template_variables={"body": ["a", "b"]},
                source_conversation_id=str(self.source_conversation.id),
            )
        self.assertIn("not assigned to the current agent", str(ctx.exception))

    @patch("api.whatsapp.template_send.send_template_message")
    def test_surfaces_graph_failure(self, mock_send):
        mock_send.side_effect = Exception("Template paused")
        with self.assertRaises(ValueError) as ctx:
            send_ws_template_to_member(
                actor_user_id=self.owner.id,
                organization_id=self.org.id,
                agent_id=self.agent.id,
                sender_id=self.ws.id,
                ws_contact_id=self.contact.id,
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
        self.member = User.objects.create_user(
            username="wa_tools_member",
            email="tools-member@example.com",
            password="x",
        )
        self.org = Organization.objects.create(name="Tools Org", owner=self.owner)
        profile = UserProfile.objects.get(user=self.owner)
        profile.organization = self.org
        profile.save(update_fields=["organization", "updated_at"])
        member_profile = UserProfile.objects.get(user=self.member)
        member_profile.organization = self.org
        member_profile.is_active = True
        member_profile.save()
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
        self.linked = WSContact.objects.create(
            ws_number=self.ws,
            number="15550003333",
            user=self.member,
        )
        self.unlinked = WSContact.objects.create(
            ws_number=self.ws,
            number="15550004444",
        )

    def test_tools_registered(self):
        from api.ai_layers.tools import list_available_tools

        names = list_available_tools()
        self.assertIn("list_whatsapp_resources", names)
        self.assertIn("list_whatsapp_templates", names)
        self.assertIn("send_ws_template_message", names)
        self.assertNotIn("list_accessible_whatsapp_senders", names)

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

    def test_list_resources_tool_nests_verified_contacts_only(self):
        from api.ai_layers.tools.list_whatsapp_resources import get_tool

        tool = get_tool(organization_id=self.org.id, user_id=self.owner.id, agent_id=self.agent.id)
        result = tool["function"]()
        self.assertEqual(len(result.resources), 1)
        resource = result.resources[0]
        self.assertEqual(resource.sender_id, self.ws.id)
        self.assertEqual(resource.agent_slug, self.agent.slug)
        self.assertEqual(len(resource.contacts), 1)
        self.assertEqual(resource.contacts[0].ws_contact_id, self.linked.id)
        self.assertEqual(resource.contacts[0].user_id, self.member.id)

    def test_list_resources_only_lines_assigned_to_agent(self):
        from api.ai_layers.models import LanguageModel
        from api.ai_layers.tools.list_whatsapp_resources import get_tool
        from api.providers.models import AIProvider

        provider = AIProvider.objects.create(name="OpenAI-wa-other-agent")
        llm = LanguageModel.objects.create(
            provider=provider, slug="gpt-wa-other", name="GPT WA Other"
        )
        other_agent = Agent.objects.create(
            name="Other Tools Agent",
            salute="hi",
            organization=self.org,
            user=self.owner,
            llm=llm,
            model_slug=llm.slug,
        )
        WSNumber.objects.create(
            organization=self.org,
            agent=other_agent,
            number="15550009999",
            platform_id="pnid-other-agent",
            name="Other",
        )

        own = get_tool(
            organization_id=self.org.id,
            user_id=self.owner.id,
            agent_id=self.agent.id,
        )["function"]()
        self.assertEqual([r.sender_id for r in own.resources], [self.ws.id])

        other = get_tool(
            organization_id=self.org.id,
            user_id=self.owner.id,
            agent_id=other_agent.id,
        )["function"]()
        self.assertEqual(len(other.resources), 1)
        self.assertEqual(other.resources[0].agent_id, other_agent.id)
        self.assertNotEqual(other.resources[0].sender_id, self.ws.id)

    def test_list_resources_requires_authenticated_int_user(self):
        from api.ai_layers.tools.list_whatsapp_resources import get_tool

        with self.assertRaises(ValueError):
            get_tool(organization_id=self.org.id, user_id="whatsapp:uuid", agent_id=self.agent.id)

    def test_list_resources_requires_agent_id(self):
        from api.ai_layers.tools.list_whatsapp_resources import get_tool

        with self.assertRaises(ValueError) as ctx:
            get_tool(organization_id=self.org.id, user_id=self.owner.id)
        self.assertIn("agent_id", str(ctx.exception))

    def test_send_tool_requires_web_user(self):
        from api.ai_layers.tools.send_ws_template_message import get_tool

        with self.assertRaises(ValueError):
            get_tool(
                conversation_id="11111111-1111-1111-1111-111111111111",
                user_id="whatsapp:abc",
                organization_id=self.org.id,
                agent_id=1,
            )

    def test_send_tool_requires_agent_id(self):
        from api.ai_layers.tools.send_ws_template_message import get_tool

        with self.assertRaises(ValueError) as ctx:
            get_tool(
                conversation_id="11111111-1111-1111-1111-111111111111",
                user_id=self.owner.id,
                organization_id=self.org.id,
            )
        self.assertIn("agent_id", str(ctx.exception))

    def test_template_tools_allowed_on_whatsapp_line_capabilities(self):
        """Grantable on the phone line; runtime still requires a linked contact."""
        from api.whatsapp.capability_tools import (
            WHATSAPP_ALLOWED_CAPABILITY_TOOLS,
            filter_capabilities_for_whatsapp,
        )
        from api.whatsapp.conversations import tool_names_from_capabilities

        for name in (
            "send_ws_template_message",
            "list_whatsapp_resources",
            "list_whatsapp_templates",
        ):
            self.assertIn(name, WHATSAPP_ALLOWED_CAPABILITY_TOOLS)

        filtered = filter_capabilities_for_whatsapp(
            [
                {
                    "name": "send_ws_template_message",
                    "type": "internal_tool",
                    "enabled": True,
                },
                {
                    "name": "list_whatsapp_resources",
                    "type": "internal_tool",
                    "enabled": True,
                },
                {
                    "name": "list_whatsapp_templates",
                    "type": "internal_tool",
                    "enabled": True,
                },
            ]
        )
        names = {c["name"] for c in filtered if c.get("enabled")}
        self.assertIn("send_ws_template_message", names)
        self.assertIn("list_whatsapp_resources", names)
        self.assertIn("list_whatsapp_templates", names)

        resolved = tool_names_from_capabilities(filtered)
        self.assertIn("send_ws_template_message", resolved)
        self.assertIn("list_whatsapp_resources", resolved)
        self.assertIn("list_whatsapp_templates", resolved)

    def test_mcp_preset_includes_whatsapp_group(self):
        from api.ai_layers.mcp_access import mcp_tool_preset_groups

        groups = {g["group"]: g["items"] for g in mcp_tool_preset_groups()}
        self.assertIn("whatsapp", groups)
        self.assertIn("send_ws_template_message", groups["whatsapp"])
        self.assertIn("list_whatsapp_resources", groups["whatsapp"])
        self.assertNotIn("list_accessible_whatsapp_senders", groups["whatsapp"])
