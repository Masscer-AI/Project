from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from api.ai_layers.models import Agent
from api.authenticate.models import Organization, Token, UserProfile
from api.messaging.models import Conversation, Message
from api.whatsapp.conversations import (
    create_whatsapp_conversation,
    get_or_create_whatsapp_conversation,
)
from api.whatsapp.models import WSContact, WSNumber, WSTemplate, WSTemplateSubscription
from api.whatsapp.template_access import (
    get_template_for_organization,
    templates_for_organization,
)
from api.whatsapp.template_registry import (
    APROBACION_PENDIENTE,
    APPROVAL_PENDING,
    EXPRESO_FISCAL_BOLETIN_SEMANAL,
    EXPRESO_FISCAL_PREFERENCIAS,
    EXPRESO_FISCAL_RECORDATORIO,
    EXPRESO_FISCAL_RESUMEN_SEMANAL,
    EXPRESO_FISCAL_SEMANAL,
    SOLICITUD_COMPLETADA,
    TASK_COMPLETED,
    WHATSAPP_TEMPLATES,
    get_template,
    list_enabled_templates,
    template_summary,
)
from api.whatsapp.template_send import (
    TemplateVariables,
    build_template_components,
    format_template_delivery_message,
    resolve_header_image_from_attachment,
    send_ws_template_to_member,
)
from api.whatsapp.template_sync import sync_default_whatsapp_templates


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
    def test_format_interpolates_approved_copy(self):
        text = format_template_delivery_message(
            TASK_COMPLETED,
            TemplateVariables(
                body=[
                    "Send a weekly summary every Monday at 7 AM",
                    "Last week there was a large number of new users.",
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
                "### Task completed\n"
                "\n"
                "I have finished completing the requested task: "
                "*Send a weekly summary every Monday at 7 AM*, here is a summary:\n"
                "\n"
                "Last week there was a large number of new users.\n"
                "\n"
                "Let me know what you think!\n"
                "\n"
                "- [Visit website](https://app.charlytoc.dev/chat?conversation="
                "11111111-1111-4111-8111-111111111111)\n"
                "\n"
                "---"
            ),
        )


class WhatsAppTemplateRegistryTests(SimpleTestCase):
    def test_task_completed_registered(self):
        tpl = get_template("task_completed_en")
        self.assertIsNotNone(tpl)
        self.assertEqual(tpl.meta_name, "task_completed")
        self.assertEqual(tpl.language_code, "en")
        self.assertEqual(tpl.header_type, "text")
        self.assertEqual(tpl.header_text, "Task completed")
        self.assertIn("*{{1}}*", tpl.body_text)
        self.assertEqual(tpl.body_variable_count, 2)
        self.assertEqual(tpl.button_variable_count, 1)
        self.assertTrue(tpl.buttons[0].use_source_conversation_id)
        self.assertEqual(tpl.buttons[0].label, "Visit website")
        self.assertEqual(
            tpl.buttons[0].url,
            "https://app.charlytoc.dev/chat?conversation=",
        )

    def test_list_enabled_includes_task_completed(self):
        ids = {t.id for t in list_enabled_templates()}
        self.assertIn(TASK_COMPLETED.id, ids)

    def test_solicitud_completada_spanish_registered(self):
        tpl = get_template("solicitud_completada_es")
        self.assertIsNotNone(tpl)
        self.assertEqual(tpl.meta_name, "solicitud_completada")
        self.assertEqual(tpl.language_code, "es")
        self.assertEqual(tpl.header_type, "text")
        self.assertEqual(tpl.header_text, "Tarea completada")
        self.assertIn("*{{1}}*", tpl.body_text)
        self.assertIn("¡Déjame saber tu opinión!", tpl.body_text)
        self.assertEqual(tpl.body_variable_count, 2)
        self.assertEqual(tpl.button_variable_count, 1)
        self.assertTrue(tpl.buttons[0].use_source_conversation_id)
        self.assertEqual(tpl.buttons[0].label, "Ver en Masscer")
        self.assertEqual(
            tpl.buttons[0].url,
            "https://app.charlytoc.dev/chat?conversation=",
        )

        ids = {t.id for t in list_enabled_templates()}
        self.assertIn(SOLICITUD_COMPLETADA.id, ids)

    def test_aprobacion_pendiente_spanish_registered(self):
        tpl = get_template("aprobacion_pendiente_es")
        self.assertIsNotNone(tpl)
        self.assertEqual(tpl.meta_name, "aprobacion_pendiente")
        self.assertEqual(tpl.language_code, "es")
        self.assertEqual(tpl.header_type, "text")
        self.assertEqual(tpl.header_text, "Aprobación pendiente")
        self.assertIn("*{{1}}*", tpl.body_text)
        self.assertIn("¿Apruebas este flujo?", tpl.body_text)
        self.assertEqual(tpl.body_variable_count, 2)
        self.assertEqual(tpl.button_variable_count, 0)
        self.assertEqual(len(tpl.buttons), 1)
        self.assertEqual(tpl.buttons[0].sub_type, "quick_reply")
        self.assertEqual(tpl.buttons[0].label, "Sí, permiso concedido.")

        ids = {t.id for t in list_enabled_templates()}
        self.assertIn(APROBACION_PENDIENTE.id, ids)

    def test_approval_pending_english_registered(self):
        tpl = get_template("approval_pending_en")
        self.assertIsNotNone(tpl)
        self.assertEqual(tpl.meta_name, "approval_pending")
        self.assertEqual(tpl.language_code, "en")
        self.assertEqual(tpl.header_type, "text")
        self.assertEqual(tpl.header_text, "Pending approval")
        self.assertIn("*{{1}}*", tpl.body_text)
        self.assertIn("Do you approve this flow?", tpl.body_text)
        self.assertEqual(tpl.body_variable_count, 2)
        self.assertEqual(tpl.button_variable_count, 0)
        self.assertEqual(len(tpl.buttons), 1)
        self.assertEqual(tpl.buttons[0].sub_type, "quick_reply")
        self.assertEqual(tpl.buttons[0].label, "Yes, permission granted")

        ids = {t.id for t in list_enabled_templates()}
        self.assertIn(APPROVAL_PENDING.id, ids)

    def test_expreso_fiscal_semanal_registered(self):
        tpl = get_template("expreso_fiscal_semanal_es_mx")
        self.assertIsNotNone(tpl)
        self.assertEqual(tpl.meta_name, "expreso_fiscal_semanal")
        self.assertEqual(tpl.language_code, "es_MX")
        self.assertEqual(tpl.category, "MARKETING")
        self.assertEqual(tpl.header_type, "image")
        self.assertTrue(tpl.requires_header_image)
        self.assertIn("*Expreso Fiscal | Integrarem*", tpl.body_text)
        self.assertEqual(tpl.buttons[0].label, "Ver boletín completo")
        self.assertEqual(
            tpl.buttons[0].url, "https://integrarem.com.mx/expreso-fiscal/"
        )
        self.assertEqual(tpl.buttons[1].label, "Escuchar resumen")
        self.assertEqual(
            tpl.buttons[1].url, "https://integrarem.com.mx/expreso-fiscal/audio/"
        )
        self.assertEqual(tpl.body_variable_count, 2)
        self.assertEqual(tpl.button_variable_count, 2)
        summary = template_summary(tpl)
        self.assertTrue(summary["requires_header_image"])
        self.assertIn(EXPRESO_FISCAL_SEMANAL.id, {t.id for t in list_enabled_templates()})

    def test_expreso_fiscal_recordatorio_registered(self):
        tpl = get_template("expreso_fiscal_recordatorio_es_mx")
        self.assertIsNotNone(tpl)
        self.assertEqual(tpl.meta_name, "expreso_fiscal_recordatorio")
        self.assertEqual(tpl.language_code, "es_MX")
        self.assertEqual(tpl.header_type, "text")
        self.assertEqual(tpl.header_text, "Expreso Fiscal | Integrarem")
        self.assertIn("Ya está disponible la edición", tpl.body_text)
        self.assertEqual(tpl.buttons[0].label, "Consultar edición")
        self.assertEqual(
            tpl.buttons[0].url, "https://integrarem.com.mx/expreso-fiscal/"
        )
        self.assertEqual(tpl.body_variable_count, 2)
        self.assertEqual(tpl.button_variable_count, 1)
        self.assertFalse(tpl.buttons[0].use_source_conversation_id)
        self.assertIn(
            EXPRESO_FISCAL_RECORDATORIO.id,
            {t.id for t in list_enabled_templates()},
        )

    def test_expreso_fiscal_preferencias_registered(self):
        tpl = get_template("expreso_fiscal_preferencias_es_mx")
        self.assertIsNotNone(tpl)
        self.assertEqual(tpl.meta_name, "expreso_fiscal_preferencias")
        self.assertEqual(tpl.category, "UTILITY")
        self.assertEqual(tpl.header_type, "text")
        self.assertEqual(tpl.header_text, "Integrarem")
        self.assertIn("comunicaciones del Expreso Fiscal", tpl.body_text)
        self.assertEqual(tpl.body_variable_count, 0)
        self.assertEqual(tpl.button_variable_count, 0)
        self.assertEqual(len(tpl.buttons), 3)
        self.assertTrue(all(b.sub_type == "quick_reply" for b in tpl.buttons))
        self.assertEqual(tpl.buttons[0].label, "Continuar recibiendo")
        self.assertEqual(tpl.buttons[1].label, "Actualizar preferencias")
        self.assertEqual(tpl.buttons[2].label, "Solicitar baja")
        self.assertIn(
            EXPRESO_FISCAL_PREFERENCIAS.id,
            {t.id for t in list_enabled_templates()},
        )

    def test_expreso_fiscal_boletin_semanal_registered(self):
        tpl = get_template("expreso_fiscal_boletin_semanal_es_mx")
        self.assertIsNotNone(tpl)
        self.assertEqual(tpl.meta_name, "expreso_fiscal_boletin_semanal")
        self.assertEqual(tpl.language_code, "es_MX")
        self.assertEqual(tpl.category, "MARKETING")
        self.assertEqual(tpl.header_type, "none")
        self.assertFalse(tpl.requires_header_image)
        self.assertEqual(tpl.body_variable_count, 1)
        self.assertEqual(tpl.button_variable_count, 0)
        self.assertEqual(len(tpl.buttons), 3)
        self.assertTrue(all(b.sub_type == "quick_reply" for b in tpl.buttons))
        self.assertEqual(tpl.buttons[0].description, "Leer por WhatsApp")
        self.assertEqual(tpl.buttons[0].label, "Leer por WhatsApp")
        self.assertIn("Hola {{1}}", tpl.body_text)
        self.assertEqual(tpl.buttons[1].description, "Solicitar resumen en audio")
        self.assertEqual(tpl.buttons[2].description, "No deseo recibir avisos")
        self.assertIn(
            EXPRESO_FISCAL_BOLETIN_SEMANAL.id,
            {t.id for t in list_enabled_templates()},
        )

    def test_expreso_fiscal_resumen_semanal_registered(self):
        tpl = get_template("expreso_fiscal_resumen_semanal_es_mx")
        self.assertIsNotNone(tpl)
        self.assertEqual(tpl.meta_name, "expreso_fiscal_resumen_semanal_es_mx")
        self.assertEqual(tpl.language_code, "es_MX")
        self.assertEqual(tpl.category, "MARKETING")
        self.assertEqual(tpl.header_type, "none")
        self.assertFalse(tpl.requires_header_image)
        self.assertEqual(tpl.body_variable_count, 7)
        self.assertEqual(tpl.button_variable_count, 0)
        self.assertEqual(len(tpl.buttons), 3)
        self.assertTrue(all(b.sub_type == "quick_reply" for b in tpl.buttons))
        self.assertEqual(tpl.buttons[0].label, "Leer boletín completo")
        self.assertEqual(tpl.buttons[1].label, "Solicitar resumen en audio")
        self.assertEqual(tpl.buttons[2].label, "No deseo recibir avisos")
        self.assertIn("*INTEGRAREM | EXPRESO FISCAL*", tpl.body_text)
        self.assertIn("{{7}}", tpl.body_text)
        self.assertIn(
            EXPRESO_FISCAL_RESUMEN_SEMANAL.id,
            {t.id for t in list_enabled_templates()},
        )

    def test_build_components_for_expreso_fiscal_semanal_with_header_image(self):
        components = build_template_components(
            EXPRESO_FISCAL_SEMANAL,
            TemplateVariables(
                body=[
                    "Al cierre del 8 de agosto de 2026",
                    "modificaciones en PLD/FT e indicadores financieros",
                ],
                buttons=["2026-08-08", "2026-08-08"],
                header_image_attachment_id="11111111-1111-1111-1111-111111111111",
            ),
            source_conversation_id="22222222-2222-2222-2222-222222222222",
            header_image={"link": "https://cdn.example.com/expreso.png"},
        )
        self.assertEqual(components[0]["type"], "header")
        self.assertEqual(
            components[0]["parameters"][0]["image"]["link"],
            "https://cdn.example.com/expreso.png",
        )
        self.assertEqual(components[1]["type"], "body")
        self.assertEqual(len(components[1]["parameters"]), 2)
        self.assertEqual(components[2]["type"], "button")
        self.assertEqual(components[2]["index"], "0")
        self.assertEqual(components[2]["parameters"][0]["text"], "2026-08-08")
        self.assertEqual(components[3]["index"], "1")

    def test_build_components_expreso_fiscal_semanal_requires_header_image(self):
        with self.assertRaises(ValueError) as ctx:
            build_template_components(
                EXPRESO_FISCAL_SEMANAL,
                TemplateVariables(
                    body=["edicion", "temas"],
                    buttons=["2026-08-08", "2026-08-08"],
                ),
                source_conversation_id=None,
            )
        self.assertIn("header_image_attachment_id", str(ctx.exception))

    def test_build_components_for_expreso_fiscal_recordatorio(self):
        components = build_template_components(
            EXPRESO_FISCAL_RECORDATORIO,
            TemplateVariables(
                body=[
                    "Al cierre del 8 de agosto de 2026",
                    "PLD/FT e indicadores financieros",
                ],
                buttons=["2026-08-08"],
            ),
            source_conversation_id=None,
        )
        self.assertEqual(len(components), 2)
        self.assertEqual(components[0]["type"], "body")
        self.assertEqual(components[1]["type"], "button")
        self.assertEqual(components[1]["parameters"][0]["text"], "2026-08-08")

    def test_build_components_for_expreso_fiscal_preferencias_no_vars(self):
        components = build_template_components(
            EXPRESO_FISCAL_PREFERENCIAS,
            TemplateVariables(),
            source_conversation_id=None,
        )
        self.assertEqual(components, [])

    def test_build_components_for_expreso_fiscal_boletin_semanal(self):
        components = build_template_components(
            EXPRESO_FISCAL_BOLETIN_SEMANAL,
            TemplateVariables(body=["Maria"]),
            source_conversation_id=None,
        )
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0]["type"], "body")
        self.assertEqual(components[0]["parameters"][0]["text"], "Maria")

    def test_build_components_for_expreso_fiscal_resumen_semanal(self):
        body = [
            "Maria",
            "14 de agosto de 2026",
            "Nuevas disposiciones en materia de PLD",
            "Publicaciones vigentes en RMF 2026",
            "Fechas y obligaciones a vigilar durante agosto",
            "$17.0530 MXN/USD · 14 ago. 2026",
            "28 dias: 6.40% · 91 dias: 6.48%",
        ]
        components = build_template_components(
            EXPRESO_FISCAL_RESUMEN_SEMANAL,
            TemplateVariables(body=body),
            source_conversation_id=None,
        )
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0]["type"], "body")
        self.assertEqual(len(components[0]["parameters"]), 7)
        self.assertEqual(components[0]["parameters"][0]["text"], "Maria")
        self.assertEqual(components[0]["parameters"][6]["text"], body[6])

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
        self.assertEqual(summary["header_text"], "Task completed")
        self.assertTrue(summary["body_text"])


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
        sync_default_whatsapp_templates()

    def test_resolve_header_image_from_attachment_uses_https_link(self):
        from django.core.files.base import ContentFile
        from django.test import override_settings

        from api.messaging.models import MessageAttachment

        att = MessageAttachment.objects.create(
            conversation=self.source_conversation,
            user=self.owner,
            kind="file",
            content_type="image/png",
            file=ContentFile(b"\x89PNG\r\n\x1a\n", name="cover.png"),
        )
        with override_settings(API_BASE_URL="https://api.example.com", MEDIA_URL="/media/"):
            image = resolve_header_image_from_attachment(
                attachment_id=str(att.id),
                conversation_id=str(self.source_conversation.id),
                phone_number_id=self.ws.platform_id,
            )
        self.assertIn("link", image)
        self.assertTrue(image["link"].startswith("https://"))

    def test_resolve_header_image_rejects_wrong_conversation(self):
        from django.core.files.base import ContentFile

        from api.messaging.models import MessageAttachment

        other = Conversation.objects.create(
            user=self.owner, organization=self.org, title="Other"
        )
        att = MessageAttachment.objects.create(
            conversation=other,
            user=self.owner,
            kind="file",
            content_type="image/png",
            file=ContentFile(b"\x89PNG\r\n\x1a\n", name="other.png"),
        )
        with self.assertRaises(ValueError) as ctx:
            resolve_header_image_from_attachment(
                attachment_id=str(att.id),
                conversation_id=str(self.source_conversation.id),
                phone_number_id=self.ws.platform_id,
            )
        self.assertIn("does not belong", str(ctx.exception))

    @patch("api.whatsapp.template_send.send_template_message")
    def test_send_image_header_template_resolves_attachment(self, mock_send):
        from django.core.files.base import ContentFile
        from django.test import override_settings

        from api.messaging.models import MessageAttachment

        mock_send.return_value = "wamid.template.img"
        att = MessageAttachment.objects.create(
            conversation=self.source_conversation,
            user=self.owner,
            kind="file",
            content_type="image/jpeg",
            file=ContentFile(b"\xff\xd8\xff", name="semanal.jpg"),
        )
        with override_settings(API_BASE_URL="https://api.example.com", MEDIA_URL="/media/"):
            result = send_ws_template_to_member(
                actor_user_id=self.owner.id,
                organization_id=self.org.id,
                agent_id=self.agent.id,
                sender_id=self.ws.id,
                ws_contact_id=self.contact.id,
                template_id="expreso_fiscal_semanal_es_mx",
                template_variables={
                    "body": [
                        "Al cierre del 8 de agosto de 2026",
                        "temas de la semana",
                    ],
                    "buttons": ["2026-08-08", "2026-08-08"],
                    "header_image_attachment_id": str(att.id),
                },
                source_conversation_id=str(self.source_conversation.id),
            )
        self.assertTrue(result.sent)
        components = mock_send.call_args.kwargs["components"]
        self.assertEqual(components[0]["type"], "header")
        self.assertIn("link", components[0]["parameters"][0]["image"])
        self.assertEqual(mock_send.call_args.kwargs["template_name"], "expreso_fiscal_semanal")
        self.assertEqual(mock_send.call_args.kwargs["language_code"], "es_MX")

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
        self.assertIn("### Task completed", msg.text)
        self.assertIn("I have finished completing the requested task:", msg.text)
        self.assertIn("*Finish weekly report*", msg.text)
        self.assertIn("All good this week", msg.text)
        self.assertIn("Let me know what you think!", msg.text)
        self.assertIn("Visit website", msg.text)
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
        self.assertIn("unavailable", str(ctx.exception).lower())

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
        sync_default_whatsapp_templates()

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

        tool = get_tool(organization_id=self.org.id)
        result = tool["function"]()
        ids = {t.template_id for t in result.templates}
        self.assertIn("task_completed_en", ids)

    def test_list_templates_tool_requires_organization_id(self):
        from api.ai_layers.tools.list_whatsapp_templates import get_tool

        with self.assertRaises(ValueError) as ctx:
            get_tool()
        self.assertIn("organization_id", str(ctx.exception))

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
        """Grantable on the phone line; kept only when contact is linked."""
        from api.whatsapp.capability_tools import filter_capabilities_for_whatsapp
        from api.whatsapp.conversations import tool_names_from_capabilities

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

        unlinked = tool_names_from_capabilities(filtered)
        self.assertNotIn("send_ws_template_message", unlinked)
        self.assertNotIn("list_whatsapp_resources", unlinked)
        self.assertNotIn("list_whatsapp_templates", unlinked)

        linked = tool_names_from_capabilities(filtered, user=self.owner)
        self.assertIn("send_ws_template_message", linked)
        self.assertIn("list_whatsapp_resources", linked)
        self.assertIn("list_whatsapp_templates", linked)

    def test_mcp_preset_includes_whatsapp_group(self):
        from api.ai_layers.mcp_access import mcp_tool_preset_groups

        groups = {g["group"]: g["items"] for g in mcp_tool_preset_groups()}
        self.assertIn("whatsapp", groups)
        self.assertIn("send_ws_template_message", groups["whatsapp"])
        self.assertIn("list_whatsapp_resources", groups["whatsapp"])
        self.assertNotIn("list_accessible_whatsapp_senders", groups["whatsapp"])


class WhatsAppTemplateSubscriptionAccessTests(TestCase):
    def setUp(self):
        from api.ai_layers.models import LanguageModel
        from api.consumption.models import Currency
        from api.providers.models import AIProvider

        Currency.objects.get_or_create(
            name="Compute Unit", defaults={"one_usd_is": 1000}
        )
        provider = AIProvider.objects.create(name="OpenAI-wa-sub")
        self.llm = LanguageModel.objects.create(
            provider=provider, slug="gpt-wa-sub", name="GPT WA Sub"
        )

        self.owner_a = User.objects.create_user(
            username="wa_sub_a", email="a@example.com", password="x"
        )
        self.owner_b = User.objects.create_user(
            username="wa_sub_b", email="b@example.com", password="x"
        )
        self.org_a = Organization.objects.create(name="Org A", owner=self.owner_a)
        self.org_b = Organization.objects.create(name="Org B", owner=self.owner_b)
        for owner, org in ((self.owner_a, self.org_a), (self.owner_b, self.org_b)):
            profile = UserProfile.objects.get(user=owner)
            profile.organization = org
            profile.save(update_fields=["organization", "updated_at"])

        self.agent_a = Agent.objects.create(
            name="Agent A",
            salute="hi",
            organization=self.org_a,
            user=self.owner_a,
            llm=self.llm,
            model_slug=self.llm.slug,
        )
        self.ws_a = WSNumber.objects.create(
            organization=self.org_a,
            agent=self.agent_a,
            number="15550001111",
            platform_id="pnid-sub-a",
        )
        self.member_a = User.objects.create_user(
            username="wa_sub_member_a", email="ma@example.com", password="x"
        )
        member_profile = UserProfile.objects.get(user=self.member_a)
        member_profile.organization = self.org_a
        member_profile.is_active = True
        member_profile.save()
        self.contact_a = WSContact.objects.create(
            ws_number=self.ws_a,
            number="15550009999",
            user=self.member_a,
        )
        self.source_a = Conversation.objects.create(
            user=self.owner_a,
            organization=self.org_a,
            title="Source A",
        )
        Conversation.objects.create(
            user=None,
            organization=self.org_a,
            ws_number=self.ws_a,
            ws_contact=self.contact_a,
            whatsapp_user_number="15550009999",
            status="active",
        )

        created, updated, unchanged = sync_default_whatsapp_templates()
        self.assertEqual(len(created), len(WHATSAPP_TEMPLATES))
        self.assertEqual(updated, [])
        self.assertEqual(unchanged, [])
        # Image header survives sync.
        semanal = WSTemplate.objects.get(slug="expreso_fiscal_semanal_es_mx")
        self.assertEqual(semanal.header_type, "image")

    def test_sync_is_idempotent(self):
        created, updated, unchanged = sync_default_whatsapp_templates()
        self.assertEqual(created, [])
        self.assertEqual(updated, [])
        self.assertEqual(len(unchanged), len(WHATSAPP_TEMPLATES))

    def test_public_template_visible_to_all_orgs(self):
        ids_a = {t.slug for t in templates_for_organization(self.org_a)}
        ids_b = {t.slug for t in templates_for_organization(self.org_b)}
        self.assertIn("task_completed_en", ids_a)
        self.assertIn("task_completed_en", ids_b)
        self.assertIsNotNone(
            get_template_for_organization("task_completed_en", self.org_a)
        )
        self.assertIsNotNone(
            get_template_for_organization("task_completed_en", self.org_b)
        )

    def test_subscribed_template_only_for_subscribed_org(self):
        tpl = WSTemplate.objects.get(slug="task_completed_en")
        WSTemplateSubscription.objects.create(
            template=tpl, organization=self.org_a
        )

        ids_a = {t.slug for t in templates_for_organization(self.org_a)}
        ids_b = {t.slug for t in templates_for_organization(self.org_b)}
        self.assertIn("task_completed_en", ids_a)
        self.assertNotIn("task_completed_en", ids_b)
        self.assertIsNotNone(
            get_template_for_organization("task_completed_en", self.org_a)
        )
        self.assertIsNone(
            get_template_for_organization("task_completed_en", self.org_b)
        )

    def test_list_tool_filters_by_subscription(self):
        from api.ai_layers.tools.list_whatsapp_templates import get_tool

        tpl = WSTemplate.objects.get(slug="expreso_fiscal_semanal_es_mx")
        WSTemplateSubscription.objects.create(
            template=tpl, organization=self.org_a
        )

        tool_a = get_tool(organization_id=self.org_a.id)
        tool_b = get_tool(organization_id=self.org_b.id)
        ids_a = {t.template_id for t in tool_a["function"]().templates}
        ids_b = {t.template_id for t in tool_b["function"]().templates}
        self.assertIn("expreso_fiscal_semanal_es_mx", ids_a)
        self.assertNotIn("expreso_fiscal_semanal_es_mx", ids_b)
        # Other public templates still visible to B.
        self.assertIn("task_completed_en", ids_b)

    @patch("api.whatsapp.template_send.send_template_message")
    def test_send_rejects_non_subscribed_org(self, mock_send):
        tpl = WSTemplate.objects.get(slug="task_completed_en")
        WSTemplateSubscription.objects.create(
            template=tpl, organization=self.org_b
        )

        with self.assertRaises(ValueError) as ctx:
            send_ws_template_to_member(
                actor_user_id=self.owner_a.id,
                organization_id=self.org_a.id,
                agent_id=self.agent_a.id,
                sender_id=self.ws_a.id,
                ws_contact_id=self.contact_a.id,
                template_id="task_completed_en",
                template_variables={"body": ["a", "b"]},
                source_conversation_id=str(self.source_a.id),
            )
        self.assertIn("unavailable", str(ctx.exception).lower())
        mock_send.assert_not_called()

    @patch("api.whatsapp.template_send.send_template_message")
    def test_send_allows_subscribed_org(self, mock_send):
        mock_send.return_value = "wamid.sub.ok"
        tpl = WSTemplate.objects.get(slug="task_completed_en")
        WSTemplateSubscription.objects.create(
            template=tpl, organization=self.org_a
        )

        result = send_ws_template_to_member(
            actor_user_id=self.owner_a.id,
            organization_id=self.org_a.id,
            agent_id=self.agent_a.id,
            sender_id=self.ws_a.id,
            ws_contact_id=self.contact_a.id,
            template_id="task_completed_en",
            template_variables={"body": ["a", "b"]},
            source_conversation_id=str(self.source_a.id),
        )
        self.assertTrue(result.sent)
        mock_send.assert_called_once()


@patch("api.whatsapp.views.FeatureFlagService.is_feature_enabled", return_value=(True, "on"))
class WhatsAppTemplatesApiTests(TestCase):
    def setUp(self):
        from api.ai_layers.models import LanguageModel
        from api.consumption.models import Currency
        from api.providers.models import AIProvider

        Currency.objects.get_or_create(
            name="Compute Unit", defaults={"one_usd_is": 1000}
        )
        provider = AIProvider.objects.create(name="OpenAI-wa-tpl-api")
        LanguageModel.objects.create(
            provider=provider, slug="gpt-wa-tpl-api", name="GPT WA Tpl API"
        )
        self.client = APIClient()
        self.owner = User.objects.create_user(
            username="wa_tpl_api_owner", email="tpl-api@example.com", password="x"
        )
        self.other = User.objects.create_user(
            username="wa_tpl_api_other", email="tpl-other@example.com", password="x"
        )
        self.org = Organization.objects.create(name="Tpl API Org", owner=self.owner)
        self.other_org = Organization.objects.create(
            name="Tpl API Other Org", owner=self.other
        )
        for user, org in ((self.owner, self.org), (self.other, self.other_org)):
            profile = UserProfile.objects.get(user=user)
            profile.organization = org
            profile.save(update_fields=["organization", "updated_at"])
        self.login_token, _ = Token.get_or_create(user=self.owner, token_type="login")
        self.other_token, _ = Token.get_or_create(user=self.other, token_type="login")
        sync_default_whatsapp_templates()

    def _auth_headers(self, token=None):
        key = (token or self.login_token).key
        return {"HTTP_AUTHORIZATION": f"Token {key}"}

    def test_lists_public_templates_for_organization(self, _mock_ff):
        response = self.client.get("/v1/whatsapp/templates", **self._auth_headers())
        self.assertEqual(response.status_code, 200)
        templates = response.json()["templates"]
        ids = {t["template_id"] for t in templates}
        self.assertIn("task_completed_en", ids)
        self.assertIn("expreso_fiscal_preferencias_es_mx", ids)
        preferencias = next(
            t for t in templates if t["template_id"] == "expreso_fiscal_preferencias_es_mx"
        )
        self.assertEqual(preferencias["meta_name"], "expreso_fiscal_preferencias")
        self.assertEqual(preferencias["language_code"], "es_MX")
        self.assertEqual(preferencias["category"], "UTILITY")
        self.assertIn("comunicaciones del Expreso Fiscal", preferencias["body_text"])
        labels = {b["label"] for b in preferencias["buttons"]}
        self.assertEqual(
            labels,
            {"Continuar recibiendo", "Actualizar preferencias", "Solicitar baja"},
        )

    def test_hides_templates_not_subscribed_by_org(self, _mock_ff):
        tpl = WSTemplate.objects.get(slug="task_completed_en")
        WSTemplateSubscription.objects.create(template=tpl, organization=self.org)

        mine = self.client.get("/v1/whatsapp/templates", **self._auth_headers())
        other = self.client.get(
            "/v1/whatsapp/templates", **self._auth_headers(self.other_token)
        )
        self.assertIn(
            "task_completed_en",
            {t["template_id"] for t in mine.json()["templates"]},
        )
        self.assertNotIn(
            "task_completed_en",
            {t["template_id"] for t in other.json()["templates"]},
        )

    def test_403_when_flag_off(self, mock_ff):
        mock_ff.return_value = (False, "off")
        response = self.client.get("/v1/whatsapp/templates", **self._auth_headers())
        self.assertEqual(response.status_code, 403)

