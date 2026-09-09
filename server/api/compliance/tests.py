from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import SimpleTestCase, TestCase
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

    def test_document_slots_follow_person_type_and_controllers(self):
        from api.compliance.models import PLDEntity, PLDPersonType, PLDRelationship
        from api.compliance.pld_document_slots import document_slots_for_entity

        fisica = PLDEntity(
            organization=self.org,
            person_type=PLDPersonType.PERSONA_FISICA,
            relationship=PLDRelationship.CLIENTE,
            metadata={
                "given_names": "Ana",
                "rfc": "LOAA800101XXX",
                "is_own_controller": False,
                "controllers": [{"name": "Luis Perez", "rfc": "PELJ800101XXX"}],
            },
        )
        fisica_keys = [s["slot_key"] for s in document_slots_for_entity(fisica)]
        self.assertEqual(
            fisica_keys,
            [
                "official_id",
                "curp",
                "constancia_fiscal",
                "comprobante_domicilio",
                "cfdi",
                "acta_nacimiento",
                "organigrama",
                "id_controlador:0",
            ],
        )
        self.assertTrue(
            next(
                s
                for s in document_slots_for_entity(fisica)
                if s["slot_key"] == "constancia_fiscal"
            )["required"]
        )

        moral = PLDEntity(
            organization=self.org,
            person_type=PLDPersonType.PERSONA_MORAL,
            relationship=PLDRelationship.CLIENTE,
            metadata={
                "legal_name": "ACME SA",
                "controllers": [
                    {"name": "Ana"},
                    {"name": "Luis"},
                ],
            },
        )
        moral_keys = [s["slot_key"] for s in document_slots_for_entity(moral)]
        self.assertIn("acta_constitutiva", moral_keys)
        self.assertIn("id_representante", moral_keys)
        self.assertIn("curp_representante", moral_keys)
        self.assertIn("cfdi", moral_keys)
        self.assertIn("matriz_accionaria", moral_keys)
        self.assertIn("id_controlador:0", moral_keys)
        self.assertIn("id_controlador:1", moral_keys)


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

    @patch("api.compliance.tasks.extract_pld_expedient_document.delay")
    @patch("api.compliance.views.send_pld_invite_email")
    def test_send_invite_and_register(self, send_email, extract_delay):
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
        self.assertEqual(send_email.call_args.kwargs["person_type"], "persona_fisica")
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
        self.assertIn("document_slots", mine.json()["results"][0])
        self.assertEqual(mine.json()["results"][0]["expedient"]["status"], "data_collection")

        entity_id = mine.json()["results"][0]["id"]
        from django.core.files.uploadedfile import SimpleUploadedFile

        too_early = self.client.post(
            f"/v1/compliance/my-expedients/{entity_id}/documents/",
            {
                "slot_key": "official_id",
                "file": SimpleUploadedFile(
                    "ine.pdf", b"%PDF-1.4", content_type="application/pdf"
                ),
            },
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )
        self.assertEqual(too_early.status_code, 400)
        self.assertEqual(too_early.json().get("error"), "save-identification-first")

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
        self.assertEqual(saved.json()["expedient"]["status"], "data_collection")

        complete = self.client.patch(
            f"/v1/compliance/my-expedients/{entity_id}/",
            {
                "metadata": {
                    "given_names": "Ana",
                    "surnames": "Lopez",
                    "date_of_birth": "1980-01-01",
                    "country_of_birth": "MX",
                    "nationality": "MX",
                    "rfc": "LOAA800101XXX",
                    "curp": "LOAA800101MDFXXX09",
                    "economic_activity": "Comercio",
                    "address": {
                        "country": "MX",
                        "postal_code": "01000",
                        "state": "Ciudad de Mexico",
                        "municipality": "Alvaro Obregon",
                        "city": "CDMX",
                        "neighborhood": "San Angel",
                        "street": "Revolucion",
                        "exterior_number": "1",
                    },
                    "identification": {
                        "document_type": "ine",
                        "document_number": "123456",
                    },
                    "is_own_controller": True,
                }
            },
            format="json",
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )
        self.assertEqual(complete.status_code, 200)
        self.assertEqual(
            complete.json()["expedient"]["status"], "document_collection"
        )
        slot_keys = [s["slot_key"] for s in complete.json()["document_slots"]]
        self.assertIn("official_id", slot_keys)
        self.assertIn("comprobante_domicilio", slot_keys)
        self.assertTrue(
            next(s for s in complete.json()["document_slots"] if s["slot_key"] == "curp")[
                "required"
            ]
        )

        from django.core.files.uploadedfile import SimpleUploadedFile

        from api.compliance.models import PLDExpedientDocument

        bad_type = self.client.post(
            f"/v1/compliance/my-expedients/{entity_id}/documents/",
            {
                "slot_key": "official_id",
                "file": SimpleUploadedFile(
                    "id.txt", b"not a document", content_type="text/plain"
                ),
            },
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )
        self.assertEqual(bad_type.status_code, 400)

        uploaded = self.client.post(
            f"/v1/compliance/my-expedients/{entity_id}/documents/",
            {
                "slot_key": "official_id",
                "file": SimpleUploadedFile(
                    "ine.pdf", b"%PDF-1.4 fake", content_type="application/pdf"
                ),
            },
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )
        self.assertEqual(uploaded.status_code, 200)
        official = next(
            s
            for s in uploaded.json()["document_slots"]
            if s["slot_key"] == "official_id"
        )
        self.assertEqual(official["document"]["original_filename"], "ine.pdf")
        self.assertEqual(official["document"]["extraction_status"], "pending")
        extract_delay.assert_called()
        self.assertEqual(PLDExpedientDocument.objects.count(), 1)
        doc_id = official["document"]["id"]

        replaced = self.client.post(
            f"/v1/compliance/my-expedients/{entity_id}/documents/",
            {
                "slot_key": "official_id",
                "file": SimpleUploadedFile(
                    "ine2.pdf", b"%PDF-1.4 two", content_type="application/pdf"
                ),
            },
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )
        self.assertEqual(replaced.status_code, 200)
        self.assertEqual(PLDExpedientDocument.objects.count(), 1)
        self.assertEqual(
            next(
                s
                for s in replaced.json()["document_slots"]
                if s["slot_key"] == "official_id"
            )["document"]["original_filename"],
            "ine2.pdf",
        )

        deleted = self.client.delete(
            f"/v1/compliance/my-expedients/{entity_id}/documents/{doc_id}/",
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertIsNone(
            next(
                s
                for s in deleted.json()["document_slots"]
                if s["slot_key"] == "official_id"
            )["document"]
        )

        unknown = self.client.post(
            f"/v1/compliance/my-expedients/{entity_id}/documents/",
            {
                "slot_key": "not_a_slot",
                "file": SimpleUploadedFile(
                    "ine.pdf", b"%PDF-1.4", content_type="application/pdf"
                ),
            },
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )
        self.assertEqual(unknown.status_code, 400)

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

    @patch("api.compliance.postal_lookup.requests.get")
    def test_postal_lookup_fills_mexico_address(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "cp": "06700",
            "estado": "Ciudad de México",
            "municipio": "Cuauhtémoc",
            "asentamientos": [
                {
                    "nombre": "Roma Norte",
                    "ciudad": "Ciudad de México",
                }
            ],
        }
        response = self.client.get(
            "/v1/compliance/postal-lookup/?country=MX&postal_code=06700",
            HTTP_AUTHORIZATION=f"Token {self.owner_token.key}",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["found"])
        self.assertEqual(payload["municipality"], "Cuauhtémoc")
        self.assertEqual(payload["city"], "Ciudad de México")
        self.assertEqual(payload["neighborhoods"], ["Roma Norte"])
        mock_get.assert_called_once()

        incomplete = self.client.get(
            "/v1/compliance/postal-lookup/?country=MX&postal_code=067",
            HTTP_AUTHORIZATION=f"Token {self.owner_token.key}",
        )
        self.assertEqual(incomplete.status_code, 200)
        self.assertFalse(incomplete.json()["found"])


class PLDDocumentExtractionTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient

        from api.authenticate.models import Token, UserProfile
        from api.compliance.models import (
            PLDEntity,
            PLDExpedient,
            PLDExpedientStatus,
            PLDPersonType,
            PLDRelationship,
        )

        _bootstrap()
        self.owner = User.objects.create_user(
            username="pld-extract-owner",
            email="pld-extract@test.com",
            password="x",
        )
        self.org = Organization.objects.create(
            name="PLD Extract Org",
            owner=self.owner,
            pld_access_enabled=True,
        )
        UserProfile.objects.update_or_create(
            user=self.owner,
            defaults={"organization": self.org},
        )
        self.token = Token.objects.create(user=self.owner)
        self.client = APIClient()
        self.entity = PLDEntity.objects.create(
            organization=self.org,
            person_type=PLDPersonType.PERSONA_MORAL,
            relationship=PLDRelationship.CLIENTE,
            user=self.owner,
            email="extract@example.com",
            metadata={
                "legal_name": "ACME SA",
                "controllers": [{"name": "Ana Lopez"}],
            },
        )
        self.expedient = PLDExpedient.objects.create(
            organization=self.org,
            entity=self.entity,
            status=PLDExpedientStatus.DOCUMENT_COLLECTION,
        )

    def test_acta_schema_round_trip(self):
        from api.compliance.document_extraction.schemas import (
            ActaConstitutivaExtraction,
            schema_for_kind,
        )

        parsed = schema_for_kind("acta_constitutiva").model_validate(
            {
                "legal_name": "ACME SA de CV",
                "shareholders": [
                    {
                        "name": "Ana Lopez",
                        "person_kind": "fisica",
                        "ownership_percentage": "60",
                    },
                    {
                        "name": "Luis Perez",
                        "ownership_percentage": "40",
                    },
                ],
                "ownership_as_of": "2020-01-15",
                "ownership_may_be_stale": True,
            }
        )
        self.assertIsInstance(parsed, ActaConstitutivaExtraction)
        self.assertEqual(parsed.shareholders[0].ownership_percentage, "60")
        self.assertEqual(len(parsed.shareholders), 2)
        with self.assertRaises(ValueError):
            schema_for_kind("unknown_kind")

    def test_official_id_schema_ignores_invented_rfc(self):
        from api.compliance.document_extraction.schemas import OfficialIdExtraction

        parsed = OfficialIdExtraction.model_validate(
            {
                "document_subtype": "ine",
                "full_name": "Ana Lopez",
                "curp": "LOAA800101MDFXXX09",
                "rfc": "SHOULD-BE-IGNORED",
                "provenances": [
                    {
                        "campo_id": "ID-nombre_completo",
                        "valor_extraido": "Ana Lopez",
                        "pagina_origen": 1,
                        "confianza_extraccion": 0.9,
                        "estado_validacion": "extraido",
                    }
                ],
            }
        )
        self.assertEqual(parsed.curp, "LOAA800101MDFXXX09")
        self.assertFalse(hasattr(parsed, "rfc"))
        self.assertEqual(parsed.provenances[0].pagina_origen, "1")

    def test_comprobante_age_helper(self):
        from datetime import date, timedelta

        from api.compliance.document_extraction.agents import _older_than_three_months

        old = (date.today() - timedelta(days=100)).isoformat()
        recent = date.today().isoformat()
        self.assertTrue(_older_than_three_months(old))
        self.assertFalse(_older_than_three_months(recent))
        self.assertIsNone(_older_than_three_months(None))

    @patch("api.compliance.tasks.extract_pld_expedient_document.delay")
    def test_upload_sets_pending_and_enqueues(self, delay):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from api.compliance.models import PLDExpedientDocument

        response = self.client.post(
            f"/v1/compliance/my-expedients/{self.entity.id}/documents/",
            {
                "slot_key": "acta_constitutiva",
                "file": SimpleUploadedFile(
                    "acta.pdf", b"%PDF-1.4", content_type="application/pdf"
                ),
            },
            HTTP_AUTHORIZATION=f"Token {self.token.key}",
        )
        self.assertEqual(response.status_code, 200)
        slot = next(
            item
            for item in response.json()["document_slots"]
            if item["slot_key"] == "acta_constitutiva"
        )
        self.assertEqual(slot["document"]["extraction_status"], "pending")
        self.assertEqual(slot["document"]["extracted_payload"], {})
        doc = PLDExpedientDocument.objects.get()
        delay.assert_called_once_with(str(doc.id))

    @patch("api.ai_layers.agent_loop.AgentLoop.create")
    def test_task_writes_acta_shareholders(self, create_loop):
        from django.core.files.base import ContentFile

        from api.ai_layers.agent_loop import AgentLoopResult
        from api.compliance.document_extraction.schemas import (
            ActaConstitutivaExtraction,
            ShareholderExtraction,
        )
        from api.compliance.models import PLDExpedientDocument
        from api.compliance.tasks import extract_pld_expedient_document

        doc = PLDExpedientDocument.objects.create(
            expedient=self.expedient,
            slot_key="acta_constitutiva",
            document_kind="acta_constitutiva",
            original_filename="acta.pdf",
            content_type="application/pdf",
            file_size=8,
            extraction_status=PLDExpedientDocument.ExtractionStatus.PENDING,
        )
        doc.file.save("acta.pdf", ContentFile(b"%PDF-1.4"), save=True)

        parsed = ActaConstitutivaExtraction(
            legal_name="ACME SA",
            shareholders=[
                ShareholderExtraction(
                    name="Ana Lopez",
                    ownership_percentage="55",
                )
            ],
            ownership_may_be_stale=True,
        )
        loop = create_loop.return_value
        loop.run.return_value = AgentLoopResult(
            output=parsed,
            messages=[],
            iterations=1,
            usage={
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        )

        extract_pld_expedient_document(str(doc.id))
        doc.refresh_from_db()
        self.assertEqual(
            doc.extraction_status,
            PLDExpedientDocument.ExtractionStatus.SUCCEEDED,
        )
        self.assertEqual(doc.extracted_payload.get("legal_name"), "ACME SA")
        self.assertEqual(
            doc.extracted_payload["shareholders"][0]["ownership_percentage"],
            "55",
        )
        create_loop.assert_called_once()
        kwargs = create_loop.call_args.kwargs
        self.assertEqual(kwargs["model"], "gpt-5.6-luna")
        self.assertEqual(kwargs["repair_model"], "gpt-5.6-luna")
        self.assertEqual(doc.extracted_payload["_meta"]["document_id"], str(doc.id))
        self.assertEqual(
            doc.extracted_payload["_meta"]["nombre_archivo"], "acta.pdf"
        )

    def test_spec_identification_schemas_cover_campo_ids(self):
        from api.compliance.document_extraction.schemas import schema_for_kind
        from api.compliance.document_extraction.spec_fields import (
            SPEC_FIELDS_BY_KIND,
            missing_spec_fields,
        )

        for kind, mapping in SPEC_FIELDS_BY_KIND.items():
            schema = schema_for_kind(kind)
            fields = schema.model_fields
            for path in mapping.values():
                root = path.split(".", 1)[0]
                self.assertIn(root, fields, f"{kind} missing {root} for {path}")
        empty = missing_spec_fields("constancia_fiscal", {})
        self.assertIn("CSF-rfc", empty)
        self.assertIn("CSF-fecha_inicio_operaciones", empty)
        filled = missing_spec_fields(
            "official_id",
            {
                "document_subtype": "ine",
                "full_name": "Ana",
                "date_of_birth": "1980-01-01",
                "nationality": "MX",
                "sex": "M",
                "address_text": "Calle 1",
                "document_number": "ABC",
                "issue_date": "2018-01-01",
                "expiry_date": "2028-01-01",
            },
        )
        self.assertEqual(filled, [])
        cfdi = schema_for_kind("cfdi")
        self.assertIn("uuid", cfdi.model_fields)
        self.assertIn("provenances", schema_for_kind("acta_constitutiva").model_fields)

    @patch("api.compliance.tasks.screen_pld_expedient.delay")
    @patch("api.compliance.tasks.extract_pld_expedient_document.delay")
    def test_confirm_documents_requires_succeeded_extraction(self, delay, screen_delay):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from api.compliance.models import PLDExpedientDocument

        too_soon = self.client.patch(
            f"/v1/compliance/my-expedients/{self.entity.id}/",
            {"action": "confirm_documents"},
            format="json",
            HTTP_AUTHORIZATION=f"Token {self.token.key}",
        )
        self.assertEqual(too_soon.status_code, 400)
        self.assertEqual(too_soon.json()["error"], "missing-documents")

        for slot_key, kind in (
            ("acta_constitutiva", "acta_constitutiva"),
            ("constancia_fiscal", "constancia_fiscal"),
            ("comprobante_domicilio", "comprobante_domicilio"),
            ("id_representante", "id_representante"),
            ("curp_representante", "curp_representante"),
            ("cfdi", "cfdi"),
            ("id_controlador:0", "id_controlador"),
        ):
            uploaded = self.client.post(
                f"/v1/compliance/my-expedients/{self.entity.id}/documents/",
                {
                    "slot_key": slot_key,
                    "file": SimpleUploadedFile(
                        f"{slot_key}.pdf", b"%PDF-1.4", content_type="application/pdf"
                    ),
                },
                HTTP_AUTHORIZATION=f"Token {self.token.key}",
            )
            self.assertEqual(uploaded.status_code, 200)

        pending = self.client.patch(
            f"/v1/compliance/my-expedients/{self.entity.id}/",
            {"action": "confirm_documents"},
            format="json",
            HTTP_AUTHORIZATION=f"Token {self.token.key}",
        )
        self.assertEqual(pending.status_code, 400)
        self.assertEqual(pending.json()["error"], "extraction-pending")

        PLDExpedientDocument.objects.filter(expedient=self.expedient).update(
            extraction_status=PLDExpedientDocument.ExtractionStatus.SUCCEEDED,
            extracted_payload={"ok": True},
        )
        still_pending = self.client.patch(
            f"/v1/compliance/my-expedients/{self.entity.id}/",
            {"action": "confirm_documents"},
            format="json",
            HTTP_AUTHORIZATION=f"Token {self.token.key}",
        )
        self.assertEqual(still_pending.status_code, 400)
        self.assertEqual(still_pending.json()["error"], "prequalification-pending")

        from api.compliance.models import PLDExpedient

        PLDExpedient.objects.filter(pk=self.expedient.pk).update(
            prequalification_status=PLDExpedient.PrequalificationStatus.SUCCEEDED,
            prequalification_payload={
                "verdict": "ready_for_list_screening",
                "summary": "ok",
                "findings": [],
            },
        )
        from api.compliance.clarifications import InviteeRequestSpec, replace_open_requests
        from api.compliance.models import PLDClarificationRequest

        replace_open_requests(
            self.expedient,
            PLDClarificationRequest.Stage.IDENTIFICATION,
            [
                InviteeRequestSpec(
                    prompt="Escribe el RFC correcto.",
                    answer_type="text",
                    target="rfc",
                )
            ],
        )
        blocked = self.client.patch(
            f"/v1/compliance/my-expedients/{self.entity.id}/",
            {"action": "confirm_documents"},
            format="json",
            HTTP_AUTHORIZATION=f"Token {self.token.key}",
        )
        self.assertEqual(blocked.status_code, 400)
        self.assertEqual(blocked.json()["error"], "clarification-pending")
        PLDClarificationRequest.objects.filter(expedient=self.expedient).update(
            status=PLDClarificationRequest.Status.CANCELLED
        )
        confirmed = self.client.patch(
            f"/v1/compliance/my-expedients/{self.entity.id}/",
            {"action": "confirm_documents"},
            format="json",
            HTTP_AUTHORIZATION=f"Token {self.token.key}",
        )
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(
            confirmed.json()["expedient"]["status"], "cross_reference"
        )
        screen_delay.assert_called_once()

    def test_deterministic_rfc_mismatch_blocks(self):
        from api.compliance.models import PLDExpedientDocument
        from api.compliance.prequalification.deterministic import (
            deterministic_findings,
            verdict_from_findings,
        )

        self.entity.metadata = {
            **self.entity.metadata,
            "rfc": "AAA010101AAA",
        }
        self.entity.save(update_fields=["metadata", "updated_at"])
        PLDExpedientDocument.objects.create(
            expedient=self.expedient,
            slot_key="constancia_fiscal",
            document_kind="constancia_fiscal",
            original_filename="csf.pdf",
            extracted_payload={"rfc": "BBB010101BBB"},
            extraction_status=PLDExpedientDocument.ExtractionStatus.SUCCEEDED,
        )
        findings = deterministic_findings(self.entity)
        codes = {item.code for item in findings}
        self.assertIn("rfc_mismatch", codes)
        self.assertEqual(verdict_from_findings(findings), "blocked")

    @patch("api.ai_layers.agent_loop.AgentLoop.create")
    def test_prequalify_task_persists_verdict(self, create_loop):
        from api.ai_layers.agent_loop import AgentLoopResult
        from api.compliance.models import PLDExpedient, PLDExpedientDocument
        from api.compliance.prequalification.schemas import PrequalificationResult
        from api.compliance.tasks import prequalify_pld_expedient

        self.entity.metadata = {
            "legal_name": "ACME SA",
            "constitution_date": "2020-01-15",
            "rfc": "AAA010101AAA",
            "economic_activity": "Comercio",
            "address": {
                "country": "MX",
                "postal_code": "01000",
                "state": "Ciudad de Mexico",
                "municipality": "Alvaro Obregon",
                "city": "CDMX",
                "neighborhood": "San Angel",
                "street": "Revolucion",
                "exterior_number": "1",
            },
            "representative": {
                "given_names": "Ana",
                "surnames": "Lopez",
                "identification": {
                    "document_type": "ine",
                    "document_number": "123",
                },
            },
            "controllers": [{"name": "Ana Lopez", "email": "ana@example.com"}],
        }
        self.entity.save(update_fields=["metadata", "updated_at"])

        for slot_key, kind in (
            ("acta_constitutiva", "acta_constitutiva"),
            ("constancia_fiscal", "constancia_fiscal"),
            ("comprobante_domicilio", "comprobante_domicilio"),
            ("id_representante", "id_representante"),
            ("curp_representante", "curp_representante"),
            ("cfdi", "cfdi"),
            ("id_controlador:0", "id_controlador"),
        ):
            PLDExpedientDocument.objects.create(
                expedient=self.expedient,
                slot_key=slot_key,
                document_kind=kind,
                original_filename=f"{slot_key}.pdf",
                extraction_status=PLDExpedientDocument.ExtractionStatus.SUCCEEDED,
                extracted_payload={"ok": True},
            )
        parsed = PrequalificationResult(
            ruleset_version="2026.1",
            verdict="needs_review",
            summary="Observaciones menores",
            findings=[],
            controllers=["Ana Lopez"],
        )
        loop = create_loop.return_value
        loop.run.return_value = AgentLoopResult(
            output=parsed,
            messages=[],
            iterations=1,
            usage={
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        )
        prequalify_pld_expedient(str(self.expedient.id))
        self.expedient.refresh_from_db()
        self.assertEqual(
            self.expedient.prequalification_status,
            PLDExpedient.PrequalificationStatus.SUCCEEDED,
        )
        self.assertEqual(
            self.expedient.prequalification_payload.get("verdict"),
            "needs_review",
        )

    def test_invitee_payload_hides_findings_and_blocks_open_requests(self):
        from api.compliance.clarifications import InviteeRequestSpec, replace_open_requests
        from api.compliance.models import PLDClarificationRequest, PLDExpedient

        PLDExpedient.objects.filter(pk=self.expedient.pk).update(
            prequalification_status=PLDExpedient.PrequalificationStatus.SUCCEEDED,
            prequalification_payload={
                "verdict": "needs_review",
                "summary": "confirma el RFC",
                "findings": [{"code": "rfc_mismatch", "severity": "blocker", "summary": "secret"}],
                "human_notes": "internal",
            },
            screening_status=PLDExpedient.PrequalificationStatus.SUCCEEDED,
            screening_payload={
                "verdict": "escalate",
                "summary": "Tu expediente sigue en revision interna.",
                "hits": [{"list_slug": "onu_csnu", "primary_name": "secret"}],
            },
        )
        replace_open_requests(
            self.expedient,
            PLDClarificationRequest.Stage.IDENTIFICATION,
            [
                InviteeRequestSpec(
                    prompt="Escribe el RFC correcto.",
                    answer_type="text",
                    target="rfc",
                )
            ],
        )
        listed = self.client.get(
            "/v1/compliance/my-expedients/",
            HTTP_AUTHORIZATION=f"Token {self.token.key}",
        )
        self.assertEqual(listed.status_code, 200)
        row = listed.json()["results"][0]
        self.assertEqual(row["expedient"]["prequalification"]["summary"], "confirma el RFC")
        self.assertNotIn("findings", row["expedient"]["prequalification"])
        self.assertNotIn("human_notes", row["expedient"]["prequalification"])
        self.assertEqual(
            row["expedient"]["screening"]["summary"],
            "Tu expediente sigue en revision interna.",
        )
        self.assertNotIn("hits", row["expedient"]["screening"])
        self.assertNotIn("verdict", row["expedient"]["screening"])
        self.assertEqual(len(row["clarification_requests"]), 1)

    def test_answer_clarification_text_updates_rfc(self):
        from api.compliance.clarifications import InviteeRequestSpec, replace_open_requests
        from api.compliance.models import PLDClarificationRequest

        created = replace_open_requests(
            self.expedient,
            PLDClarificationRequest.Stage.IDENTIFICATION,
            [
                InviteeRequestSpec(
                    prompt="Escribe el RFC correcto.",
                    answer_type="text",
                    target="rfc",
                )
            ],
        )
        request_id = str(created[0].id)
        with patch("api.compliance.tasks.prequalify_pld_expedient.delay"):
            answered = self.client.patch(
                f"/v1/compliance/my-expedients/{self.entity.id}/",
                {
                    "action": "answer_clarification",
                    "request_id": request_id,
                    "text": "AAA010101AAA",
                },
                format="json",
                HTTP_AUTHORIZATION=f"Token {self.token.key}",
            )
        self.assertEqual(answered.status_code, 200)
        self.entity.refresh_from_db()
        self.assertEqual(self.entity.metadata.get("rfc"), "AAA010101AAA")
        created[0].refresh_from_db()
        self.assertEqual(created[0].status, PLDClarificationRequest.Status.ANSWERED)

    def test_identification_packet_pdf_lists_entity_and_docs(self):
        import fitz

        from api.compliance.models import PLDExpedientDocument
        from api.compliance.packet.pdf import build_identification_packet_pdf

        PLDExpedientDocument.objects.create(
            expedient=self.expedient,
            slot_key="constancia_fiscal",
            document_kind="constancia_fiscal",
            original_filename="csf.pdf",
            extraction_status=PLDExpedientDocument.ExtractionStatus.SUCCEEDED,
        )
        pdf_bytes = build_identification_packet_pdf(self.entity)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        opened = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = "".join(page.get_text() for page in opened)
        opened.close()
        self.assertIn("ACME SA", text)
        self.assertIn("csf.pdf", text)
        self.assertIn("PLD Extract Org", text)

    @patch("api.esign.tasks.submit_signature_request_to_mifiel.delay")
    def test_clear_screening_dispatches_packet_for_signature(self, delay):
        from api.compliance.models import PLDExpedient, PLDExpedientStatus
        from api.compliance.packet import maybe_dispatch_identification_packet
        from api.esign.models import SignatureRequest, SignatureSigner

        self.entity.metadata = {
            **self.entity.metadata,
            "representative": {
                "given_names": "Ana",
                "surnames": "Lopez",
            },
            "controllers": [
                {"name": "Ana Lopez", "email": "extract@example.com"},
                {"name": "Luis Perez", "email": "luis@bc.com"},
            ],
        }
        self.entity.save(update_fields=["metadata", "updated_at"])

        PLDExpedient.objects.filter(pk=self.expedient.pk).update(
            status=PLDExpedientStatus.CROSS_REFERENCE,
            screening_status=PLDExpedient.PrequalificationStatus.SUCCEEDED,
            screening_payload={"verdict": "escalate", "summary": "internal"},
        )
        self.expedient.refresh_from_db()
        maybe_dispatch_identification_packet(self.expedient)
        self.assertFalse(SignatureRequest.objects.exists())

        PLDExpedient.objects.filter(pk=self.expedient.pk).update(
            screening_payload={"verdict": "clear", "summary": "en revision"}
        )
        self.expedient.refresh_from_db()
        maybe_dispatch_identification_packet(self.expedient)
        self.expedient.refresh_from_db()
        self.assertEqual(self.expedient.status, PLDExpedientStatus.WAITING_SIGN)
        self.assertTrue(self.expedient.packet_file)
        sr = SignatureRequest.objects.get()
        self.assertEqual(sr.signatory_email, "extract@example.com")
        self.assertEqual(sr.document_kind, "kyc_file")
        self.assertEqual(sr.signers.count(), 2)
        self.assertTrue(
            sr.signers.filter(
                email="luis@bc.com", role=SignatureSigner.Role.CONTROLLER
            ).exists()
        )
        delay.assert_called_once_with(str(sr.id))

        listed = self.client.get(
            "/v1/compliance/my-expedients/",
            HTTP_AUTHORIZATION=f"Token {self.token.key}",
        )
        row = listed.json()["results"][0]
        self.assertEqual(row["expedient"]["signing"]["signer_count"], 2)
        self.assertIn("/esign/sign/", row["expedient"]["signing"]["url"])
        self.assertNotIn("hits", row["expedient"]["screening"])
        self.assertNotIn("verdict", row["expedient"]["screening"])

    def test_pld_signature_webhook_stores_packet_and_delivers(self):
        from unittest.mock import patch

        from api.compliance.models import PLDExpedientStatus
        from api.esign.models import SignatureRequest, SignatureRequestStatus
        from api.esign.tasks import process_mifiel_webhook_event

        sr = SignatureRequest.objects.create(
            organization=self.org,
            requested_by=self.owner,
            document_kind="kyc_file",
            title="Expediente",
            signatory_name="ACME SA",
            signatory_email="extract@example.com",
            source_file=None,
            provider_document_id="mifiel-pld-1",
        )
        self.expedient.signature_request = sr
        self.expedient.status = PLDExpedientStatus.WAITING_SIGN
        self.expedient.save(
            update_fields=["signature_request", "status", "updated_at"]
        )
        with patch("api.esign.tasks.MifielClient") as mock_client_cls:
            mock_client_cls.return_value.download_signed_file.side_effect = [
                b"%PDF signed",
                b"<xml>signed</xml>",
            ]
            process_mifiel_webhook_event(
                payload={
                    "event": "document_closed",
                    "data": {
                        "external_id": str(sr.external_id),
                        "file_file_name": "expediente",
                    },
                }
            )
        sr.refresh_from_db()
        self.expedient.refresh_from_db()
        self.assertEqual(sr.status, SignatureRequestStatus.SIGNED)
        self.assertEqual(self.expedient.status, PLDExpedientStatus.DELIVERED)
        self.assertTrue(self.expedient.signed_packet)


class PLDInviteEmailTests(SimpleTestCase):
    def test_checklist_differs_by_person_type(self):
        from api.compliance.invites import pld_invite_prep_checklist

        fisica = pld_invite_prep_checklist("persona_fisica")
        moral = pld_invite_prep_checklist("persona_moral")
        self.assertTrue(any("CURP" in item for item in fisica["data"]))
        self.assertTrue(any("INE" in item for item in fisica["documents_now"]))
        self.assertTrue(any("CFDI" in item for item in fisica["documents_now"]))
        self.assertTrue(
            any("acta constitutiva" in item.lower() for item in moral["documents_now"])
        )
        self.assertTrue(any("CURP del representante" in item for item in moral["documents_now"]))
        self.assertTrue(any("Excel" in item for item in moral["documents_later"]))

    @patch("api.compliance.invites.EmailService")
    def test_invite_email_body_includes_prep_lists(self, service_cls):
        from api.compliance.invites import send_pld_invite_email

        send_pld_invite_email(
            invite_email="ana@example.com",
            organization_name="Acme",
            signup_url="https://app.example/signup?pld_invite=tok",
            person_type="persona_moral",
        )
        html = service_cls.return_value.send_email.call_args.kwargs["html"]
        self.assertIn("Datos a tener listos", html)
        self.assertIn("Acta constitutiva", html)
        self.assertIn("Se pueden cargar despues", html)
        self.assertIn("Excel", html)
        self.assertIn("Completar expediente", html)


class PublicExtractionErrorTests(SimpleTestCase):
    def test_maps_known_messages_to_stable_codes(self):
        from api.compliance.document_extraction.errors import public_extraction_error

        self.assertEqual(public_extraction_error(ValueError("File is empty")), "file-empty")
        self.assertEqual(
            public_extraction_error(ValueError("File content not available")),
            "file-unavailable",
        )
        self.assertEqual(
            public_extraction_error(ValueError("Extractor did not return structured output")),
            "no-structured-output",
        )
        self.assertEqual(
            public_extraction_error(ValueError("Failed to analyze document: boom")),
            "unreadable",
        )
        self.assertEqual(public_extraction_error(RuntimeError("timeout")), "extraction-failed")
        self.assertEqual(
            public_extraction_error(ValueError("The file cannot be reopened.")),
            "file-unavailable",
        )


class OfficialIdExtractionSchemaTests(SimpleTestCase):
    def test_coerces_pagina_origen_int_to_str(self):
        from api.compliance.document_extraction.schemas import OfficialIdExtraction

        parsed = OfficialIdExtraction.model_validate(
            {
                "full_name": "Ana Lopez",
                "provenances": [
                    {
                        "campo_id": "ID-nombre_completo",
                        "valor_extraido": "Ana Lopez",
                        "pagina_origen": 1,
                    }
                ],
            }
        )
        self.assertEqual(parsed.provenances[0].pagina_origen, "1")

    def test_curp_schema_coerces_pagina_origen_int(self):
        from api.compliance.document_extraction.schemas import CurpExtraction

        parsed = CurpExtraction.model_validate(
            {
                "curp": "LOAA800101MDFXXX09",
                "provenances": [
                    {
                        "campo_id": "CURP-curp",
                        "valor_extraido": "LOAA800101MDFXXX09",
                        "pagina_origen": 1,
                    }
                ],
            }
        )
        self.assertEqual(parsed.provenances[0].pagina_origen, "1")

    def test_openai_schema_sets_additional_properties_false(self):
        from api.compliance.document_extraction.schemas import (
            CurpExtraction,
            OfficialIdExtraction,
        )
        from api.utils.openai_functions import _response_text_format_from_pydantic

        for model in (OfficialIdExtraction, CurpExtraction):
            fmt = _response_text_format_from_pydantic(model)
            schema = fmt["schema"]
            self.assertEqual(schema.get("additionalProperties"), False, model.__name__)
            self.assertNotIn("$ref", schema, model.__name__)


