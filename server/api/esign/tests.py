from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import Client as DjangoClient
from django.test import TestCase
from rest_framework.test import APIClient

from api.ai_layers.models import LanguageModel
from api.authenticate.models import Organization
from api.consumption.models import Currency
from api.messaging.models import Conversation, MessageAttachment
from api.providers.models import AIProvider

from .mifiel_client import MifielAPIError
from .models import SignatureRequest, SignatureRequestEvent, SignatureRequestStatus
from .tasks import process_mifiel_webhook_event, submit_signature_request_to_mifiel


def _make_pdf_attachment(conversation: Conversation) -> MessageAttachment:
    return MessageAttachment.objects.create(
        conversation=conversation,
        kind="file",
        file=ContentFile(b"%PDF-1.4 fake", name="manual.pdf"),
        content_type="application/pdf",
    )


def _seed_llm_and_currency():
    # User.objects.create_user() triggers a post_save signal that auto-creates
    # an Agent, which requires at least one LanguageModel to exist.
    Currency.objects.get_or_create(name="Compute Unit", defaults={"one_usd_is": 1000})
    provider = AIProvider.objects.create(name=f"OpenAI-{LanguageModel.objects.count()}")
    return LanguageModel.objects.create(
        provider=provider,
        slug=f"gpt-esign-{LanguageModel.objects.count()}",
        name="GPT Esign",
    )


class EsignFixtureMixin:
    def setUp(self):
        _seed_llm_and_currency()
        self.user = User.objects.create_user(
            username="compliance", email="compliance@test.com", password="x"
        )
        self.org = Organization.objects.create(name="Org", owner=self.user)
        self.conversation = Conversation.objects.create(user=self.user, organization=self.org)
        self.other_conversation = Conversation.objects.create(user=self.user, organization=self.org)
        self.attachment = _make_pdf_attachment(self.conversation)


class RequestSignatureToolTests(EsignFixtureMixin, TestCase):
    @patch("api.esign.tasks.submit_signature_request_to_mifiel.delay")
    def test_creates_signature_request_and_enqueues_task(self, mock_delay):
        from api.ai_layers.tools.request_signature import _request_signature_impl

        result = _request_signature_impl(
            attachment_id=str(self.attachment.id),
            document_kind="internal_policy_manual",
            signatory_name="Jane Compliance",
            signatory_email="jane@org.com",
            signatory_rfc="XAXX010101000",
            title="Manual 2027",
            conversation_id=str(self.conversation.id),
            organization_id=str(self.org.id),
            user_id=self.user.id,
        )

        sig_request = SignatureRequest.objects.get(id=result.signature_request_id)
        self.assertEqual(sig_request.status, SignatureRequestStatus.PENDING)
        self.assertEqual(sig_request.source_file_id, self.attachment.id)
        self.assertEqual(sig_request.signatory_email, "jane@org.com")
        self.assertEqual(str(sig_request.external_id), result.external_id)
        self.assertIn(f"/esign/sign/{sig_request.id}", result.signing_url)
        mock_delay.assert_called_once_with(str(sig_request.id))

        message = self.conversation.messages.filter(metadata__source="esign_mifiel").first()
        self.assertIsNotNone(message)
        self.assertIn(result.signing_url, message.text)
        self.assertIn("Jane Compliance", message.text)

    @patch("api.esign.tasks.submit_signature_request_to_mifiel.delay")
    def test_rejects_attachment_from_other_conversation(self, mock_delay):
        from api.ai_layers.tools.request_signature import _request_signature_impl

        with self.assertRaises(ValueError):
            _request_signature_impl(
                attachment_id=str(self.attachment.id),
                document_kind="other",
                signatory_name="Jane",
                signatory_email="jane@org.com",
                signatory_rfc=None,
                title=None,
                conversation_id=str(self.other_conversation.id),
                organization_id=str(self.org.id),
                user_id=self.user.id,
            )
        mock_delay.assert_not_called()

    @patch("api.esign.tasks.submit_signature_request_to_mifiel.delay")
    def test_rejects_non_pdf_attachment(self, mock_delay):
        from api.ai_layers.tools.request_signature import _request_signature_impl

        docx_attachment = MessageAttachment.objects.create(
            conversation=self.conversation,
            kind="file",
            file=ContentFile(b"not a pdf", name="manual.docx"),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        with self.assertRaises(ValueError):
            _request_signature_impl(
                attachment_id=str(docx_attachment.id),
                document_kind="other",
                signatory_name="Jane",
                signatory_email="jane@org.com",
                signatory_rfc=None,
                title=None,
                conversation_id=str(self.conversation.id),
                organization_id=str(self.org.id),
                user_id=self.user.id,
            )
        mock_delay.assert_not_called()


class SubmitSignatureRequestTaskTests(EsignFixtureMixin, TestCase):
    def _make_request(self) -> SignatureRequest:
        return SignatureRequest.objects.create(
            organization=self.org,
            requested_by=self.user,
            document_kind="other",
            signatory_name="Jane Compliance",
            signatory_email="jane@org.com",
            source_file=self.attachment,
        )

    @patch("api.esign.tasks.MifielClient")
    def test_success_sets_provider_document_id_and_widget_id(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.create_document.return_value = {
            "id": "mifiel-doc-1",
            "state": "pending",
            "signers": [{"id": "s1", "widget_id": "EVjDwA8RhK", "email": "jane@org.com"}],
        }

        sig_request = self._make_request()
        submit_signature_request_to_mifiel(str(sig_request.id))

        sig_request.refresh_from_db()
        self.assertEqual(sig_request.provider_document_id, "mifiel-doc-1")
        self.assertEqual(sig_request.provider_widget_id, "EVjDwA8RhK")
        self.assertEqual(sig_request.metadata["create_response"]["id"], "mifiel-doc-1")

        mock_client.create_document.assert_called_once()
        self.assertEqual(
            mock_client.create_document.call_args.kwargs["send_invites"], False
        )

    @patch("api.esign.tasks.MifielClient")
    def test_missing_widget_id_leaves_field_blank(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.create_document.return_value = {"id": "mifiel-doc-1", "state": "pending", "signers": []}

        sig_request = self._make_request()
        submit_signature_request_to_mifiel(str(sig_request.id))

        sig_request.refresh_from_db()
        self.assertEqual(sig_request.provider_widget_id, "")

    @patch("api.esign.tasks.MifielClient")
    def test_api_error_sets_status_error(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.create_document.side_effect = MifielAPIError(422, "bad request")

        sig_request = self._make_request()
        submit_signature_request_to_mifiel(str(sig_request.id))

        sig_request.refresh_from_db()
        self.assertEqual(sig_request.status, SignatureRequestStatus.ERROR)
        self.assertIn("bad request", sig_request.metadata["error"])


class ProcessMifielWebhookEventTests(EsignFixtureMixin, TestCase):
    def _make_request(self) -> SignatureRequest:
        return SignatureRequest.objects.create(
            organization=self.org,
            requested_by=self.user,
            document_kind="other",
            title="Manual 2027",
            signatory_name="Jane Compliance",
            signatory_email="jane@org.com",
            source_file=self.attachment,
            provider_document_id="mifiel-doc-1",
        )

    @patch("api.esign.tasks.MifielClient")
    def test_document_closed_attaches_signed_files(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.download_signed_file.side_effect = [b"%PDF signed", b"<xml>signed</xml>"]

        sig_request = self._make_request()
        payload = {
            "event": "document_closed",
            "data": {
                "id": "mifiel-doc-1",
                "external_id": str(sig_request.external_id),
                "file_file_name": "manual",
                "signed_at": "2027-01-01T00:00:00Z",
            },
        }
        process_mifiel_webhook_event(payload=payload)

        sig_request.refresh_from_db()
        self.assertEqual(sig_request.status, SignatureRequestStatus.SIGNED)
        self.assertIsNotNone(sig_request.signed_file_id)
        self.assertIsNotNone(sig_request.signed_file_xml_id)
        self.assertAlmostEqual(
            (sig_request.signed_file.expires_at - sig_request.signed_at).days,
            365 * 10,
            delta=1,
        )
        self.assertEqual(
            SignatureRequestEvent.objects.filter(
                signature_request=sig_request, event_type="document_closed"
            ).count(),
            1,
        )

        message = self.conversation.messages.filter(metadata__source="esign_mifiel").first()
        self.assertIsNotNone(message)
        self.assertEqual(len(message.attachments), 2)

    @patch("api.esign.tasks.MifielClient")
    def test_document_closed_is_idempotent(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.download_signed_file.side_effect = [b"%PDF signed", b"<xml>signed</xml>"]

        sig_request = self._make_request()
        payload = {
            "event": "document_closed",
            "data": {
                "id": "mifiel-doc-1",
                "external_id": str(sig_request.external_id),
                "file_file_name": "manual",
                "signed_at": "2027-01-01T00:00:00Z",
            },
        }
        process_mifiel_webhook_event(payload=payload)
        process_mifiel_webhook_event(payload=payload)

        # Two events logged (webhook retried), but download only called once.
        self.assertEqual(mock_client.download_signed_file.call_count, 2)  # one call per file, first delivery only
        self.assertEqual(
            SignatureRequestEvent.objects.filter(signature_request=sig_request).count(), 2
        )

    def test_unknown_external_id_is_dropped(self):
        payload = {
            "event": "document_closed",
            "data": {"id": "x", "external_id": "00000000-0000-0000-0000-000000000000"},
        }
        # Should not raise, and must not create any attachment/event.
        process_mifiel_webhook_event(payload=payload)
        self.assertEqual(SignatureRequestEvent.objects.count(), 0)

    def test_signer_rejected_updates_status(self):
        sig_request = self._make_request()
        payload = {
            "event": "signer_rejected",
            "data": {"document": "mifiel-doc-1", "document_external_id": str(sig_request.external_id)},
        }
        process_mifiel_webhook_event(payload=payload)
        sig_request.refresh_from_db()
        self.assertEqual(sig_request.status, SignatureRequestStatus.REJECTED)


class MifielWebhookViewTests(EsignFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()

    def _make_request(self) -> SignatureRequest:
        return SignatureRequest.objects.create(
            organization=self.org,
            requested_by=self.user,
            document_kind="other",
            signatory_name="Jane Compliance",
            signatory_email="jane@org.com",
            source_file=self.attachment,
            provider_document_id="mifiel-doc-1",
        )

    @patch("api.esign.views.process_mifiel_webhook_event.delay")
    def test_webhook_enqueues_task_and_returns_200(self, mock_delay):
        sig_request = self._make_request()
        payload = {
            "event": "document_closed",
            "data": {"id": "mifiel-doc-1", "external_id": str(sig_request.external_id)},
        }
        response = self.client.post("/v1/esign/webhook", payload, format="json")
        self.assertEqual(response.status_code, 200)
        mock_delay.assert_called_once_with(payload=payload)

    def test_webhook_rejects_non_post(self):
        response = self.client.get("/v1/esign/webhook")
        self.assertEqual(response.status_code, 405)

    def test_webhook_rejects_invalid_json(self):
        response = self.client.post(
            "/v1/esign/webhook", data=b"not json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)


class RegisterWebhooksAdminViewTests(EsignFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.staff = User.objects.create_superuser(
            username="staff", email="staff@test.com", password="x"
        )
        self.django_client = DjangoClient()
        self.django_client.force_login(self.staff)

    @patch("api.esign.admin.MifielClient")
    def test_registers_missing_webhooks_and_skips_existing(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.list_webhooks.return_value = [{"callback_type": "document_closed"}]

        response = self.django_client.get(
            "/admin/esign/signaturerequest/register-webhooks/", follow=True
        )
        self.assertEqual(response.status_code, 200)

        # 3 missing types registered, 1 already-registered type skipped.
        self.assertEqual(mock_client.register_webhook.call_count, 3)
        registered_types = {
            call.kwargs["callback_type"] for call in mock_client.register_webhook.call_args_list
        }
        self.assertEqual(
            registered_types, {"signer_completed", "signer_rejected", "document_deleted"}
        )

    @patch("api.esign.admin.MifielClient")
    def test_reports_error_when_credentials_missing(self, mock_client_cls):
        mock_client_cls.side_effect = MifielAPIError(0, "MIFIEL_APP_ID / MIFIEL_API_KEY are not configured.")

        response = self.django_client.get(
            "/admin/esign/signaturerequest/register-webhooks/", follow=True
        )
        self.assertEqual(response.status_code, 200)
        messages_text = [str(m) for m in response.context["messages"]]
        self.assertTrue(any("not configured" in m for m in messages_text))

    def test_requires_staff_login(self):
        anon_client = DjangoClient()
        response = anon_client.get("/admin/esign/signaturerequest/register-webhooks/")
        self.assertEqual(response.status_code, 302)  # redirected to admin login


class PublicSignatureRequestViewTests(EsignFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.anon_client = DjangoClient()

    def _make_request(self, **overrides) -> SignatureRequest:
        defaults = dict(
            organization=self.org,
            requested_by=self.user,
            document_kind="internal_policy_manual",
            title="Manual 2027",
            signatory_name="Jane Compliance",
            signatory_email="jane@org.com",
            source_file=self.attachment,
        )
        defaults.update(overrides)
        return SignatureRequest.objects.create(**defaults)

    def test_returns_minimal_payload_without_auth(self):
        sig_request = self._make_request(provider_widget_id="EVjDwA8RhK")

        # No Authorization header at all — this must work for a completely
        # anonymous external signer, not just "no login".
        response = self.anon_client.get(f"/v1/esign/sign/{sig_request.id}/")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["id"], str(sig_request.id))
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["title"], "Manual 2027")
        self.assertEqual(data["signatory_name"], "Jane Compliance")
        self.assertEqual(data["organization_name"], self.org.name)
        self.assertEqual(data["widget_id"], "EVjDwA8RhK")
        self.assertTrue(data["widget_ready"])

        # PII / internal fields must never leak through this public endpoint.
        self.assertNotIn("signatory_email", data)
        self.assertNotIn("signatory_rfc", data)
        self.assertNotIn("provider_document_id", data)
        self.assertNotIn("metadata", data)

    def test_widget_not_ready_before_mifiel_upload_completes(self):
        sig_request = self._make_request()  # provider_widget_id blank by default

        response = self.anon_client.get(f"/v1/esign/sign/{sig_request.id}/")
        data = response.json()
        self.assertEqual(data["status"], "pending")
        self.assertIsNone(data["widget_id"])
        self.assertFalse(data["widget_ready"])

    def test_signed_status_reports_widget_not_ready(self):
        sig_request = self._make_request(
            provider_widget_id="EVjDwA8RhK", status=SignatureRequestStatus.SIGNED
        )

        response = self.anon_client.get(f"/v1/esign/sign/{sig_request.id}/")
        data = response.json()
        self.assertEqual(data["status"], "signed")
        # widget_ready is only true while still pending — no reason to re-render
        # the signing widget once the document is already signed.
        self.assertFalse(data["widget_ready"])

    def test_unknown_id_returns_404(self):
        response = self.anon_client.get(
            "/v1/esign/sign/00000000-0000-0000-0000-000000000000/"
        )
        self.assertEqual(response.status_code, 404)
