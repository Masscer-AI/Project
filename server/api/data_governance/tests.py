from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone

from api.authenticate.models import Organization, Token, UserProfile
from api.data_governance.models import DataExportJob, OrganizationDataPolicy
from api.data_governance.schemas import parse_export_manifest, parse_policy_patch
from api.data_governance.exporters.conversations import ConversationsExporter
from api.data_governance.schemas import DataExportManifestSchema, ExportCategoriesSchema, ConversationsExportCategory, AgentsExportCategory
from api.messaging.models import Conversation
from datetime import date
from pathlib import Path
import tempfile


class DataGovernanceSchemaTests(TestCase):
    def test_policy_min_attachment_days(self):
        with self.assertRaises(Exception):
            parse_policy_patch({"attachment_retention_days": 3})

    def test_export_manifest_requires_category(self):
        with self.assertRaises(Exception):
            parse_export_manifest(
                {
                    "date_from": "2025-01-01",
                    "date_to": "2025-01-31",
                    "categories": {
                        "conversations": {"enabled": False},
                        "agents": {"enabled": False},
                        "completions": {"enabled": False},
                        "documents": {"enabled": False},
                    },
                }
            )


class DataGovernanceApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="dgowner",
            email="dgowner@example.com",
            password="pass",
        )
        self.org = Organization.objects.create(name="DG Org", owner=self.user)
        UserProfile.objects.create(user=self.user, organization=self.org)
        self.token, _ = Token.get_or_create(user=self.user, token_type="permanent")
        self.client = Client()

    def _auth(self, method, url, data=None):
        headers = {"HTTP_AUTHORIZATION": f"Token {self.token.key}"}
        if data is not None:
            return getattr(self.client, method)(
                url, data=data, content_type="application/json", **headers
            )
        return getattr(self.client, method)(url, **headers)

    def test_get_policy_creates_default(self):
        url = f"/v1/data-governance/organizations/{self.org.id}/policy/"
        resp = self._auth("get", url)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIsNone(body["deleted_conversation_retention_days"])
        self.assertTrue(
            OrganizationDataPolicy.objects.filter(organization=self.org).exists()
        )

    def test_patch_policy(self):
        url = f"/v1/data-governance/organizations/{self.org.id}/policy/"
        resp = self._auth(
            "patch",
            url,
            {"deleted_conversation_retention_days": 30, "attachment_retention_days": 14},
        )
        self.assertEqual(resp.status_code, 200)
        policy = OrganizationDataPolicy.objects.get(organization=self.org)
        self.assertEqual(policy.deleted_conversation_retention_days, 30)
        self.assertEqual(policy.attachment_retention_days, 14)

    def test_create_export_job(self):
        url = f"/v1/data-governance/organizations/{self.org.id}/exports/"
        resp = self._auth(
            "post",
            url,
            {
                "notify_via": "app",
                "manifest": {
                    "date_from": "2025-01-01",
                    "date_to": "2025-01-31",
                    "categories": {
                        "conversations": {"enabled": True, "include_attachments": False},
                        "agents": {"enabled": True},
                    },
                },
            },
        )
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(DataExportJob.objects.filter(organization=self.org).count(), 1)


class ConversationsExporterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="exporter", password="pass")
        self.org = Organization.objects.create(name="Export Org", owner=self.user)
        UserProfile.objects.create(user=self.user, organization=self.org)

    def test_exports_member_conversation_without_organization_fk(self):
        """App chats often have organization=null; export must still include them."""
        today = timezone.now().date()
        conv = Conversation.objects.create(
            user=self.user,
            organization=None,
            last_message_at=timezone.now(),
        )
        manifest = DataExportManifestSchema(
            date_from=today - timedelta(days=7),
            date_to=today,
            categories=ExportCategoriesSchema(
                conversations=ConversationsExportCategory(enabled=True),
                agents=AgentsExportCategory(enabled=False),
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            result = ConversationsExporter().export(
                organization=self.org,
                manifest=manifest,
                output_dir=Path(tmp),
            )
        self.assertEqual(result.summary.get("conversations_exported"), 1)
        self.assertTrue(any("conversations" in a.relative_path for a in result.artifacts))


class RetentionPurgeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="purge", password="pass")
        self.org = Organization.objects.create(name="Purge Org", owner=self.user)

    def test_purge_deleted_conversations(self):
        from api.data_governance.services.retention import purge_deleted_conversations_for_org

        policy = OrganizationDataPolicy.objects.create(
            organization=self.org,
            deleted_conversation_retention_days=7,
        )
        conv = Conversation.objects.create(
            organization=self.org,
            user=self.user,
            status="deleted",
            deleted_at=timezone.now() - timedelta(days=10),
        )
        count = purge_deleted_conversations_for_org(policy)
        self.assertEqual(count, 1)
        self.assertFalse(Conversation.objects.filter(id=conv.id).exists())
