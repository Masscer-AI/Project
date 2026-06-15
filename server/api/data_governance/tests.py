from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone

from api.authenticate.models import Organization, Token, UserProfile
from api.data_governance.models import DataExportJob, OrganizationDataPolicy
from api.data_governance.schemas import parse_export_manifest, parse_policy_patch
from api.data_governance.exporters.conversations import ConversationsExporter
from api.data_governance.exporters.knowledge_base import (
    CompletionsExporter,
    DocumentTemplatesExporter,
    DocumentsExporter,
)
from api.data_governance.schemas import (
    AgentsExportCategory,
    CompletionsExportCategory,
    DataExportManifestSchema,
    DocumentTemplatesExportCategory,
    DocumentsExportCategory,
    ExportCategoriesSchema,
    ConversationsExportCategory,
)
from api.messaging.models import Conversation
from api.ai_layers.models import Agent, LanguageModel
from api.providers.models import AIProvider
from api.finetuning.models import Completion, CompletionAssignment
from api.rag.models import Chunk, Collection, Document
from api.document_templates.models import DocumentTemplate
from django.core.files.uploadedfile import SimpleUploadedFile
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
                        "document_templates": {"enabled": False},
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


class KnowledgeBaseExporterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="kbexport", password="pass")
        self.org = Organization.objects.create(name="KB Org", owner=self.user)
        UserProfile.objects.create(user=self.user, organization=self.org)
        self.provider = AIProvider.objects.create(name="OpenAI")
        self.llm = LanguageModel.objects.create(
            provider=self.provider,
            name="Test LLM",
            slug="test-llm-kb",
        )
        self.agent = Agent.objects.create(
            name="Org Agent",
            salute="hello",
            user=self.user,
            organization=self.org,
            llm=self.llm,
            model_slug=self.llm.slug,
        )

    def _manifest(self, **category_kwargs) -> DataExportManifestSchema:
        today = timezone.now().date()
        defaults = {
            "conversations": ConversationsExportCategory(enabled=False),
            "agents": AgentsExportCategory(enabled=False),
            "completions": CompletionsExportCategory(enabled=False),
            "documents": DocumentsExportCategory(enabled=False),
            "document_templates": DocumentTemplatesExportCategory(enabled=False),
        }
        defaults.update(category_kwargs)
        return DataExportManifestSchema(
            date_from=today - timedelta(days=7),
            date_to=today,
            categories=ExportCategoriesSchema(**defaults),
        )

    def test_exports_org_completion(self):
        completion = Completion.objects.create(prompt="p", answer="a", approved=True)
        CompletionAssignment.objects.create(completion=completion, agent=self.agent)

        with tempfile.TemporaryDirectory() as tmp:
            result = CompletionsExporter().export(
                organization=self.org,
                manifest=self._manifest(
                    completions=CompletionsExportCategory(enabled=True)
                ),
                output_dir=Path(tmp),
            )
        self.assertEqual(result.summary.get("completions_exported"), 1)

    def test_exports_member_personal_collection_document(self):
        collection, _ = Collection.get_or_create_personal_collection(user=self.user)
        doc = Document.objects.create(
            collection=collection,
            name="Policy",
            text="Some knowledge",
        )
        Chunk.objects.create(document=doc, content="chunk one")

        with tempfile.TemporaryDirectory() as tmp:
            result = DocumentsExporter().export(
                organization=self.org,
                manifest=self._manifest(
                    documents=DocumentsExportCategory(enabled=True)
                ),
                output_dir=Path(tmp),
            )
        self.assertEqual(result.summary.get("documents_exported"), 1)

    def test_exports_org_document_template(self):
        template = DocumentTemplate.objects.create(
            organization=self.org,
            created_by=self.user,
            name="Contract",
            file=SimpleUploadedFile(
                "contract.docx",
                b"fake-docx",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
            original_filename="contract.docx",
        )

        with tempfile.TemporaryDirectory() as tmp:
            result = DocumentTemplatesExporter().export(
                organization=self.org,
                manifest=self._manifest(
                    document_templates=DocumentTemplatesExportCategory(enabled=True)
                ),
                output_dir=Path(tmp),
            )
        self.assertEqual(result.summary.get("document_templates_exported"), 1)
        self.assertEqual(result.summary.get("document_template_files_exported"), 1)


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
