from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import TestCase

from api.ai_layers.models import LanguageModel
from api.ai_layers.tools.list_attachments import _list_attachments_impl
from api.ai_layers.tools.list_folio_documents import _list_folio_documents_impl
from api.ai_layers.tools.update_folio_document import _update_folio_document_impl
from api.ai_layers.tools.update_folio_status import _update_folio_status_impl
from api.authenticate.models import Organization
from api.compliance.folio import ingest_compliance_attachment
from api.compliance.models import ComplianceFolio, FolioDocument, FolioDocumentStatus, FolioStatus
from api.consumption.models import Currency
from api.messaging.attachment_access import user_can_access_attachment
from api.messaging.models import Conversation, MessageAttachment
from api.providers.models import AIProvider


def _bootstrap():
    Currency.objects.get_or_create(
        name="Compute Unit", defaults={"one_usd_is": 1000}
    )
    provider, _ = AIProvider.objects.get_or_create(name="OpenAI-folio")
    LanguageModel.objects.get_or_create(
        slug="gpt-folio",
        defaults={"provider": provider, "name": "GPT Folio"},
    )


class ComplianceFolioTests(TestCase):
    def setUp(self):
        _bootstrap()
        self.user = User.objects.create_user(
            username="folio-user", email="folio@test.com", password="x"
        )
        self.org = Organization.objects.create(name="Folio Org", owner=self.user)
        self.compliance_conv = Conversation.objects.create(
            user=self.user,
            organization=self.org,
            title="Compliance",
            metadata={"surface": "compliance", "related_agents": []},
        )
        self.chat_conv = Conversation.objects.create(
            user=self.user,
            organization=self.org,
            title="Regular chat",
        )

    def _file_att(self, conversation, name="ine.pdf"):
        return MessageAttachment.objects.create(
            conversation=conversation,
            user=self.user,
            kind="file",
            file=ContentFile(b"%PDF-1.4", name=name),
            content_type="application/pdf",
        )

    def test_ingest_links_compliance_upload_not_regular_chat(self):
        chat_att = self._file_att(self.chat_conv, "notes.pdf")
        self.assertIsNone(ingest_compliance_attachment(chat_att, actor=self.user))
        self.assertEqual(FolioDocument.objects.count(), 0)

        att = self._file_att(self.compliance_conv)
        doc = ingest_compliance_attachment(att, actor=self.user)
        self.assertIsNotNone(doc)
        att.refresh_from_db()
        self.assertTrue(att.metadata.get("compliance"))
        self.assertIsNone(att.expires_at)
        folio = ComplianceFolio.objects.get(
            organization=self.org, subject_user=self.user
        )
        self.assertEqual(folio.status, FolioStatus.OPEN)
        self.assertEqual(doc.folio_id, folio.id)
        self.compliance_conv.refresh_from_db()
        self.assertEqual(self.compliance_conv.metadata.get("folio_id"), str(folio.id))

        again = ingest_compliance_attachment(att, actor=self.user)
        self.assertEqual(again.id, doc.id)
        self.assertEqual(FolioDocument.objects.count(), 1)

    def test_chat_agents_cannot_list_or_read_folio_files(self):
        att = self._file_att(self.compliance_conv)
        ingest_compliance_attachment(att, actor=self.user)

        listed = _list_attachments_impl(
            kind="document",
            user_id=self.user.id,
            conversation_id=str(self.chat_conv.id),
        )
        self.assertEqual(listed.attachments, [])

        self.assertFalse(
            user_can_access_attachment(
                att,
                user=self.user,
                conversation_id=str(self.chat_conv.id),
            )
        )
        self.assertFalse(
            user_can_access_attachment(
                att,
                user=self.user,
                conversation_id=str(self.compliance_conv.id),
            )
        )
        self.assertTrue(
            user_can_access_attachment(
                att,
                user=self.user,
                conversation_id=str(self.compliance_conv.id),
                include_compliance_evidence=True,
            )
        )

        listed_ok = _list_attachments_impl(
            kind="document",
            user_id=self.user.id,
            conversation_id=str(self.compliance_conv.id),
            include_compliance_evidence=True,
        )
        self.assertEqual(len(listed_ok.attachments), 1)
        self.assertEqual(listed_ok.attachments[0].attachment_id, str(att.id))

    def test_folio_tools_list_and_update(self):
        att = self._file_att(self.compliance_conv)
        doc = ingest_compliance_attachment(att, actor=self.user)

        listed = _list_folio_documents_impl(
            user_id=self.user.id, organization_id=self.org.id
        )
        self.assertEqual(listed.folio_status, FolioStatus.OPEN)
        self.assertEqual(len(listed.documents), 1)

        updated = _update_folio_document_impl(
            folio_document_id=str(doc.id),
            user_id=self.user.id,
            organization_id=self.org.id,
            document_kind="ine",
            status=FolioDocumentStatus.VALIDATED,
            notes="Legible",
        )
        self.assertTrue(updated.success)
        doc.refresh_from_db()
        self.assertEqual(doc.document_kind, "ine")
        self.assertEqual(doc.status, FolioDocumentStatus.VALIDATED)

        folio_upd = _update_folio_status_impl(
            user_id=self.user.id,
            organization_id=self.org.id,
            status=FolioStatus.IN_REVIEW,
            notes="Waiting on CSF",
        )
        self.assertEqual(folio_upd.status, FolioStatus.IN_REVIEW)
        folio = ComplianceFolio.objects.get(pk=listed.folio_id)
        self.assertEqual(folio.notes, "Waiting on CSF")
