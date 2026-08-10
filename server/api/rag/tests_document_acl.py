import json
from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase

from api.ai_layers.models import LanguageModel
from api.authenticate.models import Organization, Role, RoleAssignment, Token, UserProfile
from api.consumption.models import Currency
from api.messaging.models import Conversation
from api.providers.models import AIProvider
from api.rag.access import (
    apply_document_ownership,
    documents_accessible_q,
    user_can_access_document,
)
from api.rag.models import Collection, Document


def _ensure_user_bootstrap():
    Currency.objects.get_or_create(
        name="Compute Unit", defaults={"one_usd_is": 1000}
    )
    provider, _ = AIProvider.objects.get_or_create(name="OpenAI")
    llm, _ = LanguageModel.objects.get_or_create(
        slug="test-llm-doc-acl",
        defaults={
            "provider": provider,
            "name": "Test LLM Doc ACL",
        },
    )
    return llm


class DocumentAclHelperTests(TestCase):
    def setUp(self):
        self.rag_chroma_patch = patch("api.rag.models.chroma_client", None)
        self.rag_chroma_patch.start()
        self.brief_patch = patch("api.rag.signals.async_generate_document_brief.delay")
        self.brief_patch.start()
        _ensure_user_bootstrap()
        self.owner = User.objects.create_user(username="owner", password="x")
        self.member = User.objects.create_user(username="member", password="x")
        self.outsider = User.objects.create_user(username="outsider", password="x")
        self.org = Organization.objects.create(name="ACL Org", owner=self.owner)
        UserProfile.objects.filter(user=self.member).update(organization=self.org)
        self.member = User.objects.select_related("profile").get(pk=self.member.pk)
        self.role_a = Role.objects.create(organization=self.org, name="Analysts")
        self.role_b = Role.objects.create(organization=self.org, name="Managers")
        RoleAssignment.objects.create(
            user=self.member,
            organization=self.org,
            role=self.role_a,
            from_date=date.today(),
        )
        self.owner_collection, _ = Collection.get_or_create_personal_collection(
            user=self.owner
        )

    def tearDown(self):
        self.brief_patch.stop()
        self.rag_chroma_patch.stop()

    def _doc(self, **kwargs):
        defaults = {
            "collection": self.owner_collection,
            "text": "hello knowledge",
            "name": "doc",
            "created_by": self.owner,
            "total_tokens": 1,
        }
        defaults.update(kwargs)
        return Document.objects.create(**defaults)

    def test_personal_hidden_from_other_members(self):
        doc = self._doc(visibility=Document.Visibility.PERSONAL)
        self.assertTrue(user_can_access_document(self.owner, doc))
        self.assertFalse(user_can_access_document(self.member, doc))
        self.assertFalse(
            Document.objects.filter(documents_accessible_q(self.member), pk=doc.pk).exists()
        )

    def test_organization_visible_to_members(self):
        doc = self._doc(
            visibility=Document.Visibility.ORGANIZATION,
            organization=self.org,
        )
        self.assertTrue(user_can_access_document(self.member, doc))
        self.assertTrue(user_can_access_document(self.owner, doc))
        self.assertFalse(user_can_access_document(self.outsider, doc))

    def test_roles_visible_only_to_matching_role_or_owner(self):
        doc = self._doc(
            visibility=Document.Visibility.ROLES,
            organization=self.org,
        )
        doc.allowed_roles.set([self.role_a])
        self.assertTrue(user_can_access_document(self.member, doc))
        self.assertTrue(user_can_access_document(self.owner, doc))

        doc.allowed_roles.set([self.role_b])
        self.assertFalse(user_can_access_document(self.member, doc))
        self.assertTrue(user_can_access_document(self.owner, doc))

    def test_apply_roles_requires_role_ids(self):
        doc = self._doc()
        with self.assertRaises(ValueError):
            apply_document_ownership(
                doc,
                user=self.owner,
                visibility=Document.Visibility.ROLES,
                role_ids=[],
            )

    def test_apply_organization_sets_fields(self):
        doc = self._doc()
        apply_document_ownership(
            doc,
            user=self.owner,
            visibility=Document.Visibility.ORGANIZATION,
        )
        doc.refresh_from_db()
        self.assertEqual(doc.visibility, Document.Visibility.ORGANIZATION)
        self.assertEqual(doc.organization_id, self.org.id)
        self.assertEqual(doc.allowed_roles.count(), 0)


class DocumentAclApiTests(TestCase):
    def setUp(self):
        self.rag_chroma_patch = patch("api.rag.models.chroma_client", None)
        self.rag_chroma_patch.start()
        self.brief_patch = patch("api.rag.signals.async_generate_document_brief.delay")
        self.brief_patch.start()
        self.client = Client()
        _ensure_user_bootstrap()
        self.owner = User.objects.create_user(username="api-owner", password="x")
        self.member = User.objects.create_user(username="api-member", password="x")
        self.org = Organization.objects.create(name="API Org", owner=self.owner)
        UserProfile.objects.filter(user=self.member).update(organization=self.org)
        self.member = User.objects.select_related("profile").get(pk=self.member.pk)
        self.owner_token = Token.objects.create(user=self.owner, token_type="permanent")
        self.member_token = Token.objects.create(user=self.member, token_type="permanent")
        self.owner_collection, _ = Collection.get_or_create_personal_collection(
            user=self.owner
        )
        self.ff_patch = patch(
            "api.authenticate.services.FeatureFlagService.is_feature_enabled",
            return_value=(True, "test"),
        )
        self.ff_patch.start()

    def tearDown(self):
        self.ff_patch.stop()
        self.brief_patch.stop()
        self.rag_chroma_patch.stop()

    def _auth(self, token: Token):
        return {"HTTP_AUTHORIZATION": f"Token {token.key}"}

    def _create_doc(self, **kwargs):
        defaults = {
            "collection": self.owner_collection,
            "created_by": self.owner,
            "total_tokens": 1,
        }
        defaults.update(kwargs)
        return Document.objects.create(**defaults)

    def test_list_respects_personal_visibility(self):
        personal = self._create_doc(
            text="personal-only",
            name="mine",
            visibility=Document.Visibility.PERSONAL,
        )
        org_doc = self._create_doc(
            text="org-wide",
            name="ours",
            visibility=Document.Visibility.ORGANIZATION,
            organization=self.org,
        )

        member_resp = self.client.get(
            "/v1/rag/documents/",
            **self._auth(self.member_token),
        )
        self.assertEqual(member_resp.status_code, 200)
        ids = {d["id"] for d in member_resp.json()}
        self.assertNotIn(personal.id, ids)
        self.assertIn(org_doc.id, ids)

        owner_resp = self.client.get(
            "/v1/rag/documents/",
            **self._auth(self.owner_token),
        )
        self.assertEqual(owner_resp.status_code, 200)
        owner_ids = {d["id"] for d in owner_resp.json()}
        self.assertIn(personal.id, owner_ids)
        self.assertIn(org_doc.id, owner_ids)

    def test_update_ownership_via_put(self):
        doc = self._create_doc(
            text="to-update",
            name="upd",
            visibility=Document.Visibility.PERSONAL,
        )
        role = Role.objects.create(organization=self.org, name="Editors")
        resp = self.client.put(
            f"/v1/rag/documents/{doc.id}/",
            data=json.dumps(
                {
                    "action": "update_ownership",
                    "visibility": "roles",
                    "role_ids": [str(role.id)],
                }
            ),
            content_type="application/json",
            **self._auth(self.owner_token),
        )
        self.assertEqual(resp.status_code, 200)
        doc.refresh_from_db()
        self.assertEqual(doc.visibility, Document.Visibility.ROLES)
        self.assertEqual(list(doc.allowed_roles.values_list("id", flat=True)), [role.id])

    def test_attach_forbidden_without_access(self):
        doc = self._create_doc(
            text="secret",
            name="secret",
            visibility=Document.Visibility.PERSONAL,
        )
        conv = Conversation.objects.create(user=self.member)
        resp = self.client.post(
            "/v1/messaging/attachments/link/",
            data=json.dumps(
                {
                    "conversation_id": str(conv.id),
                    "kind": "rag_document",
                    "rag_document_id": doc.id,
                }
            ),
            content_type="application/json",
            **self._auth(self.member_token),
        )
        self.assertEqual(resp.status_code, 403)

    def test_attach_allowed_with_org_visibility(self):
        doc = self._create_doc(
            text="shared",
            name="shared",
            visibility=Document.Visibility.ORGANIZATION,
            organization=self.org,
        )
        conv = Conversation.objects.create(user=self.member)
        resp = self.client.post(
            "/v1/messaging/attachments/link/",
            data=json.dumps(
                {
                    "conversation_id": str(conv.id),
                    "kind": "rag_document",
                    "rag_document_id": doc.id,
                }
            ),
            content_type="application/json",
            **self._auth(self.member_token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("attachment", resp.json())
