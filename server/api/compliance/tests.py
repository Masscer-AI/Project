from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import TestCase
from unittest.mock import patch

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


class PLDFoundationTests(TestCase):
    def setUp(self):
        _bootstrap()
        self.user = User.objects.create_user(
            username="pld-user", email="pld@test.com", password="x"
        )
        self.org = Organization.objects.create(name="PLD Org", owner=self.user)

    def test_unique_self_entity_per_org(self):
        from django.core.exceptions import ValidationError
        from django.db import IntegrityError, transaction

        from api.compliance.models import PLDEntity, PLDPersonType

        PLDEntity.objects.create(
            organization=self.org,
            person_type=PLDPersonType.PERSONA_MORAL,
            relationship=None,
        )
        with self.assertRaises((IntegrityError, ValidationError)):
            with transaction.atomic():
                PLDEntity.objects.create(
                    organization=self.org,
                    person_type=PLDPersonType.PERSONA_MORAL,
                    relationship=None,
                )

    def test_expedient_unique_per_org_entity_allows_counterparties(self):
        from django.db import IntegrityError, transaction

        from api.compliance.models import (
            PLDEntity,
            PLDExpedient,
            PLDPersonType,
            PLDRelationship,
            VulnerableActivity,
        )

        self_entity = PLDEntity.objects.create(
            organization=self.org,
            person_type=PLDPersonType.PERSONA_MORAL,
            relationship=None,
            metadata={"legal_name": "PLD Org SA"},
        )
        client = PLDEntity.objects.create(
            organization=self.org,
            person_type=PLDPersonType.PERSONA_FISICA,
            relationship=PLDRelationship.CLIENTE,
            metadata={"name": "Cliente Uno"},
        )
        PLDExpedient.objects.create(
            organization=self.org,
            entity=self_entity,
            vulnerable_activity=VulnerableActivity.ACTIVOS_VIRTUALES,
        )
        PLDExpedient.objects.create(
            organization=self.org,
            entity=client,
        )
        self.assertEqual(PLDExpedient.objects.filter(organization=self.org).count(), 2)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PLDExpedient.objects.create(
                    organization=self.org,
                    entity=client,
                )

    def test_metadata_validation(self):
        from django.core.exceptions import ValidationError

        from api.compliance.models import PLDEntity, PLDPersonType
        from api.compliance.pld_metadata import normalize_pld_entity_metadata

        self.assertEqual(normalize_pld_entity_metadata("persona_fisica", None), {})
        self.assertEqual(normalize_pld_entity_metadata("persona_moral", {}), {})
        with self.assertRaises(ValueError):
            normalize_pld_entity_metadata("persona_moral", ["not", "an", "object"])
        with self.assertRaises(ValueError):
            normalize_pld_entity_metadata(
                "persona_moral", {"controllers": "not-a-list"}
            )

        with self.assertRaises(ValidationError):
            PLDEntity.objects.create(
                organization=self.org,
                person_type=PLDPersonType.PERSONA_MORAL,
                relationship=None,
                metadata=["bad"],
            )


class PLDEntityAPITests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient

        from api.authenticate.models import Token, UserProfile

        _bootstrap()
        self.owner = User.objects.create_user(
            username="pld-api-owner", email="pld-api@test.com", password="x"
        )
        self.outsider = User.objects.create_user(
            username="pld-api-out", email="pld-out@test.com", password="x"
        )
        self.org = Organization.objects.create(
            name="PLD API Org",
            owner=self.owner,
            pld_access_enabled=True,
        )
        UserProfile.objects.update_or_create(
            user=self.owner,
            defaults={"organization": self.org},
        )
        self.owner_token = Token.objects.create(user=self.owner)
        self.outsider_token = Token.objects.create(user=self.outsider)
        self.client = APIClient()

    def test_list_and_create_counterparty(self):
        from api.compliance.models import PLDEntity, PLDExpedient

        listed = self.client.get(
            "/v1/compliance/entities/",
            HTTP_AUTHORIZATION=f"Token {self.owner_token.key}",
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["results"], [])

        created = self.client.post(
            "/v1/compliance/entities/",
            {
                "person_type": "persona_moral",
                "relationship": "cliente",
                "email": "acme@example.com",
                "metadata": {"legal_name": "ACME SA"},
            },
            format="json",
            HTTP_AUTHORIZATION=f"Token {self.owner_token.key}",
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["relationship"], "cliente")
        self.assertEqual(created.json()["email"], "acme@example.com")
        self.assertEqual(created.json()["metadata"].get("legal_name"), "ACME SA")
        self.assertIsNotNone(created.json().get("expedient"))
        self.assertEqual(PLDEntity.objects.filter(organization=self.org).count(), 1)
        self.assertEqual(PLDExpedient.objects.filter(organization=self.org).count(), 1)

        listed = self.client.get(
            "/v1/compliance/entities/",
            HTTP_AUTHORIZATION=f"Token {self.owner_token.key}",
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()["results"]), 1)

    def test_create_rejects_missing_relationship(self):
        response = self.client.post(
            "/v1/compliance/entities/",
            {"person_type": "persona_fisica", "metadata": {"name": "Ana"}},
            format="json",
            HTTP_AUTHORIZATION=f"Token {self.owner_token.key}",
        )
        self.assertEqual(response.status_code, 400)

    def test_list_404_without_pld_access(self):
        response = self.client.get(
            "/v1/compliance/entities/",
            HTTP_AUTHORIZATION=f"Token {self.outsider_token.key}",
        )
        self.assertEqual(response.status_code, 404)

    def test_create_rejects_missing_email(self):
        response = self.client.post(
            "/v1/compliance/entities/",
            {
                "person_type": "persona_moral",
                "relationship": "cliente",
                "metadata": {"legal_name": "No Email SA"},
            },
            format="json",
            HTTP_AUTHORIZATION=f"Token {self.owner_token.key}",
        )
        self.assertEqual(response.status_code, 400)

    def test_delete_counterparty(self):
        from api.compliance.models import PLDEntity, PLDPersonType, PLDRelationship

        entity = PLDEntity.objects.create(
            organization=self.org,
            person_type=PLDPersonType.PERSONA_MORAL,
            relationship=PLDRelationship.PROVEEDOR,
            email="gone@example.com",
            metadata={"legal_name": "Gone SA"},
        )
        response = self.client.delete(
            f"/v1/compliance/entities/{entity.id}/",
            HTTP_AUTHORIZATION=f"Token {self.owner_token.key}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PLDEntity.objects.filter(pk=entity.pk).exists())

    @patch("api.compliance.views.send_pld_invite_email")
    def test_send_invite_and_register(self, send_email):
        from api.compliance.models import PLDInvite

        created = self.client.post(
            "/v1/compliance/entities/",
            {
                "person_type": "persona_fisica",
                "relationship": "cliente",
                "email": "counterparty@example.com",
                "metadata": {"name": "Ana"},
            },
            format="json",
            HTTP_AUTHORIZATION=f"Token {self.owner_token.key}",
        )
        entity_id = created.json()["id"]
        invited = self.client.post(
            f"/v1/compliance/entities/{entity_id}/invite/",
            {},
            format="json",
            HTTP_AUTHORIZATION=f"Token {self.owner_token.key}",
        )
        self.assertEqual(invited.status_code, 200)
        send_email.assert_called_once()
        signup_url = send_email.call_args.kwargs["signup_url"]
        self.assertIn("pld_invite=", signup_url)
        raw = signup_url.split("pld_invite=", 1)[1]
        public = self.client.get(f"/v1/compliance/invites/public/?token={raw}")
        self.assertEqual(public.status_code, 200)
        self.assertTrue(public.json().get("invite_valid"))

        registered = self.client.post(
            "/v1/compliance/invites/public/",
            {
                "token": raw,
                "password": "CorrectHorse1",
                "confirm_password": "CorrectHorse1",
            },
            format="json",
        )
        self.assertEqual(registered.status_code, 201)
        invite = PLDInvite.objects.get(email="counterparty@example.com")
        self.assertEqual(invite.status, PLDInvite.Status.ACCEPTED)
        from api.authenticate.models import UserProfile

        user = User.objects.get(email="counterparty@example.com")
        profile = UserProfile.objects.get(user=user)
        self.assertIsNone(profile.organization_id)

        from api.authenticate.models import Token

        token = Token.objects.create(user=user)
        mine = self.client.get(
            "/v1/compliance/my-expedients/",
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )
        self.assertEqual(mine.status_code, 200)
        self.assertEqual(len(mine.json()["results"]), 1)
        self.assertEqual(mine.json()["results"][0]["person_type"], "persona_fisica")
        self.assertIn("metadata", mine.json()["results"][0])

        entity_id = mine.json()["results"][0]["id"]
        saved = self.client.patch(
            f"/v1/compliance/my-expedients/{entity_id}/",
            {
                "metadata": {
                    "given_names": "Ana",
                    "paternal_surname": "Lopez",
                    "rfc": "LOAA800101XXX",
                    "curp": "LOAA800101MDFXXX09",
                    "nationality": "MX",
                    "address": {
                        "city": "CDMX",
                        "postal_code": "01000",
                        "country": "MX",
                    },
                    "is_own_controller": True,
                }
            },
            format="json",
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["metadata"].get("given_names"), "Ana")
        self.assertEqual(saved.json()["metadata"].get("name"), "Ana Lopez")

        forbidden = self.client.patch(
            f"/v1/compliance/my-expedients/{entity_id}/",
            {"metadata": {"given_names": "Hacker"}},
            format="json",
            HTTP_AUTHORIZATION=f"Token {self.owner_token.key}",
        )
        self.assertEqual(forbidden.status_code, 404)

    def test_list_404_for_member_without_compliance_flag(self):
        from api.authenticate.models import Token, UserProfile

        member = User.objects.create_user(
            username="pld-no-role", email="pld-no-role@test.com", password="x"
        )
        UserProfile.objects.update_or_create(
            user=member,
            defaults={"organization": self.org, "is_active": True},
        )
        token = Token.objects.create(user=member)
        response = self.client.get(
            "/v1/compliance/entities/",
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )
        self.assertEqual(response.status_code, 404)

    def test_list_200_for_member_with_compliance_flag(self):
        from django.utils import timezone

        from api.authenticate.models import Role, RoleAssignment, Token, UserProfile

        member = User.objects.create_user(
            username="pld-with-role", email="pld-with-role@test.com", password="x"
        )
        UserProfile.objects.update_or_create(
            user=member,
            defaults={"organization": self.org, "is_active": True},
        )
        role = Role.objects.create(
            organization=self.org,
            name="Compliance",
            enabled=True,
            capabilities=["organization-compliance-access"],
        )
        RoleAssignment.objects.create(
            user=member,
            organization=self.org,
            role=role,
            from_date=timezone.now().date(),
        )
        token = Token.objects.create(user=member)
        response = self.client.get(
            "/v1/compliance/entities/",
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])


