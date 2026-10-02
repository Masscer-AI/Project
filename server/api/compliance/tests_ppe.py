from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings

from api.authenticate.models import Organization
from api.compliance.ppe import ppe_targets, run_ppe_screening
from api.compliance.tests import _bootstrap


class PpeTargetTests(SimpleTestCase):
    def test_moral_includes_representative_and_controllers(self):
        entity = SimpleNamespace(
            person_type="persona_moral",
            metadata={
                "representative": {
                    "given_names": "Ana",
                    "surnames": "Lopez",
                    "date_of_birth": "1980-01-02",
                    "curp": "LOPA800102MDFXXX00",
                    "rfc": "LOPA800102XX1",
                },
                "controllers": [
                    {"name": "Luis Perez", "rfc": "PELX800101XX1"},
                    {"name": "  "},
                ],
            },
        )
        rows = ppe_targets(entity)
        self.assertEqual([row["role"] for row in rows], ["representante", "beneficiario_controlador"])
        self.assertEqual(rows[0]["properties"]["birthDate"], ["1980-01-02"])
        self.assertIn("LOPA800102MDFXXX00", rows[0]["properties"]["idNumber"])
        self.assertEqual(rows[1]["name"], "Luis Perez")

    def test_fisica_skips_controller_when_self(self):
        entity = SimpleNamespace(
            person_type="persona_fisica",
            metadata={
                "given_names": "Mara",
                "surnames": "Diaz",
                "nationality": "MX",
                "is_own_controller": True,
                "controller": {"name": "Someone Else"},
            },
        )
        rows = ppe_targets(entity)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["role"], "titular")
        self.assertEqual(rows[0]["properties"]["nationality"], ["MX"])

    def test_fisica_includes_other_controller(self):
        entity = SimpleNamespace(
            person_type="persona_fisica",
            metadata={
                "given_names": "Mara",
                "surnames": "Diaz",
                "is_own_controller": False,
                "controller": {"name": "Otro Control", "rfc": "COTX800101XX1"},
            },
        )
        rows = ppe_targets(entity)
        self.assertEqual([row["role"] for row in rows], ["titular", "beneficiario_controlador"])


@override_settings(
    OPEN_SANCTIONS_API_KEY="test-key",
    OPEN_SANCTIONS_API_URL="https://api.opensanctions.org",
)
class PpeMatchTests(SimpleTestCase):
    @patch("api.compliance.ppe.requests.post")
    def test_match_peps_counts_only_matches(self, post):
        response = MagicMock()
        response.json.return_value = {
            "responses": {
                "q0": {
                    "status": 200,
                    "results": [
                        {
                            "id": "os-1",
                            "caption": "Ana Lopez",
                            "score": 0.91,
                            "match": True,
                            "properties": {"topics": ["role.pep"]},
                        },
                        {
                            "id": "os-2",
                            "caption": "Other",
                            "score": 0.4,
                            "match": False,
                            "properties": {},
                        },
                    ],
                }
            }
        }
        post.return_value = response
        entity = SimpleNamespace(
            person_type="persona_fisica",
            metadata={"given_names": "Ana", "surnames": "Lopez", "is_own_controller": True},
        )
        payload = run_ppe_screening(entity)
        self.assertEqual(payload["checks"][0]["hit_count"], 1)
        self.assertEqual(payload["checks"][0]["hits"][0]["caption"], "Ana Lopez")
        url = post.call_args.args[0]
        self.assertTrue(url.endswith("/match/peps"))
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "ApiKey test-key")


class PpeEntityFlagTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient

        from api.authenticate.models import Token, UserProfile

        _bootstrap()
        self.owner = User.objects.create_user(
            username="ppe-owner", email="ppe-owner@test.com", password="x"
        )
        self.org = Organization.objects.create(
            name="PPE Org",
            owner=self.owner,
            pld_access_enabled=True,
        )
        UserProfile.objects.update_or_create(
            user=self.owner,
            defaults={"organization": self.org},
        )
        self.token = Token.objects.create(user=self.owner)
        self.client = APIClient()

    def test_create_stores_ppe_flag(self):
        created = self.client.post(
            "/v1/compliance/entities/",
            {
                "person_type": "persona_moral",
                "relationship": "proveedor",
                "email": "vendor@example.com",
                "ppe_screening_enabled": True,
                "metadata": {"legal_name": "Vendor SA"},
            },
            format="json",
            HTTP_AUTHORIZATION=f"Token {self.token.key}",
        )
        self.assertEqual(created.status_code, 201)
        self.assertTrue(created.json()["ppe_screening_enabled"])

        skipped = self.client.post(
            "/v1/compliance/entities/",
            {
                "person_type": "persona_fisica",
                "relationship": "cliente",
                "email": "person@example.com",
                "metadata": {"name": "Mara"},
            },
            format="json",
            HTTP_AUTHORIZATION=f"Token {self.token.key}",
        )
        self.assertEqual(skipped.status_code, 201)
        self.assertFalse(skipped.json()["ppe_screening_enabled"])
