from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from api.authenticate.models import Organization, Token, UserProfile
from api.compliance.models import (
    PLDEntity,
    PLDExpedient,
    PLDExpedientDocument,
    PLDExpedientStatus,
)
from api.compliance.tests import _bootstrap


class PLDRunHistoryTests(TestCase):
    def setUp(self):
        _bootstrap()
        self.owner = User.objects.create_user(
            username="runs-owner", email="runs-owner@test.com", password="x"
        )
        self.org = Organization.objects.create(
            name="Runs Org", owner=self.owner, pld_access_enabled=True
        )
        UserProfile.objects.update_or_create(
            user=self.owner, defaults={"organization": self.org}
        )
        self.auth = f"Token {Token.objects.create(user=self.owner).key}"
        self.client = APIClient()

    def _create_counterparty(self):
        created = self.client.post(
            "/v1/compliance/entities/",
            {
                "person_type": "persona_moral",
                "relationship": "proveedor",
                "email": "supplier@example.com",
                "metadata": {"legal_name": "Proveedor SA", "rfc": "PRO010101AAA"},
            },
            format="json",
            HTTP_AUTHORIZATION=self.auth,
        )
        return PLDEntity.objects.get(pk=created.json()["id"])

    def _deliver(self, exp):
        exp.status = PLDExpedientStatus.DELIVERED
        exp.save(update_fields=["status", "updated_at"])

    def _new_run(self, entity):
        return self.client.post(
            f"/v1/compliance/entities/{entity.id}/expedients/",
            {},
            format="json",
            HTTP_AUTHORIZATION=self.auth,
        )

    def test_versions_are_unique_per_entity(self):
        entity = self._create_counterparty()
        self._deliver(entity.current_expedient())
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PLDExpedient.objects.create(
                    organization=self.org,
                    entity=entity,
                    version=1,
                    status=PLDExpedientStatus.DELIVERED,
                )

    @patch("api.compliance.views.send_pld_invite_email")
    def test_new_run_is_refused_while_current_run_is_open(self, send_email):
        entity = self._create_counterparty()
        response = self._new_run(entity)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "expedient-open")
        self.assertEqual(entity.expedients.count(), 1)
        send_email.assert_not_called()

    @patch("api.compliance.views.send_pld_invite_email")
    def test_new_run_keeps_the_old_one_and_emails_the_counterparty(self, send_email):
        entity = self._create_counterparty()
        entity.metadata = {
            **entity.metadata,
            "truthfulness_accepted": True,
            "declares_pep": False,
            "notice_invoices_done": True,
        }
        entity.save()
        first = entity.current_expedient()
        doc = PLDExpedientDocument(
            expedient=first, slot_key="acta", document_kind="acta_constitutiva"
        )
        doc.file.save("acta.pdf", ContentFile(b"%PDF-1.4"), save=True)
        first.risk_payload = {"semaphore": "green"}
        first.save(update_fields=["risk_payload", "updated_at"])
        self._deliver(first)

        response = self._new_run(entity)

        self.assertEqual(response.status_code, 201)
        send_email.assert_called_once()
        entity.refresh_from_db()
        current = entity.current_expedient()
        self.assertEqual(current.version, 2)
        self.assertEqual(current.status, PLDExpedientStatus.DATA_COLLECTION)
        self.assertEqual(current.documents.count(), 0)
        self.assertEqual(response.json()["expedient"]["id"], str(current.id))
        first.refresh_from_db()
        self.assertEqual(first.status, PLDExpedientStatus.DELIVERED)
        self.assertEqual(first.documents.count(), 1)
        self.assertIsNotNone(first.completed_at)
        self.assertEqual(first.entity_snapshot["metadata"]["truthfulness_accepted"], True)
        self.assertEqual(entity.metadata["legal_name"], "Proveedor SA")
        self.assertEqual(entity.metadata["rfc"], "PRO010101AAA")
        self.assertFalse(entity.metadata["truthfulness_accepted"])
        self.assertIsNone(entity.metadata["declares_pep"])
        self.assertFalse(entity.metadata["notice_invoices_done"])

        history = self.client.get(
            f"/v1/compliance/entities/{entity.id}/expedients/",
            HTTP_AUTHORIZATION=self.auth,
        )
        self.assertEqual(history.status_code, 200)
        rows = history.json()["results"]
        self.assertEqual([row["version"] for row in rows], [2, 1])
        self.assertEqual(rows[1]["semaphore"], "green")
        self.assertEqual(len(rows[1]["files"]["documents"]), 1)

    @patch("api.compliance.views.send_pld_invite_email")
    def test_self_entity_new_run_sends_no_email(self, send_email):
        started = self.client.post(
            "/v1/compliance/start-process/",
            {},
            format="json",
            HTTP_AUTHORIZATION=self.auth,
        )
        entity = PLDEntity.objects.get(pk=started.json()["id"])
        self._deliver(entity.current_expedient())

        response = self._new_run(entity)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(entity.current_expedient().version, 2)
        send_email.assert_not_called()

    def test_start_process_reuses_the_open_run(self):
        for _ in range(2):
            started = self.client.post(
                "/v1/compliance/start-process/",
                {},
                format="json",
                HTTP_AUTHORIZATION=self.auth,
            )
            self.assertEqual(started.status_code, 200)
        entity = PLDEntity.objects.get(pk=started.json()["id"])
        self.assertEqual(entity.expedients.count(), 1)

    def test_run_downloads_are_scoped_to_the_entity(self):
        entity = self._create_counterparty()
        other = PLDEntity.objects.create(
            organization=self.org,
            person_type="persona_moral",
            relationship="cliente",
            email="other@example.com",
        )
        other_run = PLDExpedient.objects.create(organization=self.org, entity=other)

        packet = self.client.get(
            f"/v1/compliance/entities/{entity.id}/expedients/{other_run.id}/packet/",
            HTTP_AUTHORIZATION=self.auth,
        )
        self.assertEqual(packet.status_code, 404)

        run = entity.current_expedient()
        bundle = self.client.get(
            f"/v1/compliance/entities/{entity.id}/expedients/{run.id}/bundle/",
            HTTP_AUTHORIZATION=self.auth,
        )
        self.assertEqual(bundle.status_code, 200)
        self.assertEqual(bundle["Content-Type"], "application/zip")

    def test_signing_freezes_the_run(self):
        from api.compliance.packet.dispatch import mark_expedient_signed
        from api.esign.models import SignatureRequest

        entity = self._create_counterparty()
        run = entity.current_expedient()
        sr = SignatureRequest.objects.create(
            organization=self.org,
            requested_by=self.owner,
            document_kind="kyc_file",
            title="Expediente",
            signatory_name="Proveedor SA",
            signatory_email="supplier@example.com",
            source_file=None,
        )
        run.signature_request = sr
        run.status = PLDExpedientStatus.WAITING_SIGN
        run.save(update_fields=["signature_request", "status", "updated_at"])

        mark_expedient_signed(sr, pdf_bytes=b"%PDF-1.4")

        run.refresh_from_db()
        self.assertEqual(run.status, PLDExpedientStatus.DELIVERED)
        self.assertIsNotNone(run.completed_at)
        self.assertEqual(run.entity_snapshot["metadata"]["legal_name"], "Proveedor SA")


class PLDInviteeRunTests(TestCase):
    def setUp(self):
        _bootstrap()
        owner = User.objects.create_user(
            username="invitee-runs-owner", email="owner-ir@test.com", password="x"
        )
        org = Organization.objects.create(
            name="Invitee Runs Org", owner=owner, pld_access_enabled=True
        )
        self.invitee = User.objects.create_user(
            username="invitee-runs", email="invitee-ir@test.com", password="x"
        )
        self.entity = PLDEntity.objects.create(
            organization=org,
            person_type="persona_moral",
            relationship="cliente",
            email="invitee-ir@test.com",
            user=self.invitee,
            metadata={"legal_name": "Cliente SA"},
        )
        self.run = PLDExpedient.objects.create(organization=org, entity=self.entity)
        self.auth = f"Token {Token.objects.create(user=self.invitee).key}"
        self.client = APIClient()

    def _patch(self, action):
        return self.client.patch(
            f"/v1/compliance/my-expedients/{self.entity.id}/",
            {"action": action},
            format="json",
            HTTP_AUTHORIZATION=self.auth,
        )

    def test_invitee_starts_a_new_run_and_sees_history(self):
        self.assertEqual(self._patch("start_new_run").status_code, 409)
        self.run.status = PLDExpedientStatus.DELIVERED
        self.run.save(update_fields=["status", "updated_at"])

        response = self._patch("start_new_run")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["version"] for row in response.json()["runs"]], [2, 1])
        self.assertEqual(response.json()["expedient"]["status"], "data_collection")

    def test_reset_does_not_erase_a_finished_run(self):
        self.run.status = PLDExpedientStatus.DELIVERED
        self.run.save(update_fields=["status", "updated_at"])

        response = self._patch("reset_expedient")

        self.assertEqual(response.status_code, 409)
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, PLDExpedientStatus.DELIVERED)

    def test_invitee_downloads_a_past_packet(self):
        self.run.packet_file.save("packet.pdf", ContentFile(b"%PDF-1.4"), save=False)
        self.run.status = PLDExpedientStatus.DELIVERED
        self.run.save()
        self._patch("start_new_run")

        response = self.client.get(
            f"/v1/compliance/my-expedients/{self.entity.id}/expedients/{self.run.id}/packet/",
            HTTP_AUTHORIZATION=self.auth,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
