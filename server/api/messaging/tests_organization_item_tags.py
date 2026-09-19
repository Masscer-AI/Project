import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import Client, SimpleTestCase, TestCase

from api.ai_layers.models import Agent, LanguageModel
from api.authenticate.models import Organization, Token, UserProfile
from api.consumption.models import Currency
from api.messaging.models import Conversation, MessageAttachment, Tag
from api.providers.models import AIProvider
from api.rag.models import Collection, Document


def _bootstrap():
    Currency.objects.get_or_create(name="Compute Unit", defaults={"one_usd_is": 1000})
    provider, _ = AIProvider.objects.get_or_create(name="OpenAI-org-tags")
    llm, _ = LanguageModel.objects.get_or_create(
        slug="gpt-org-item-tags",
        defaults={"provider": provider, "name": "GPT Org Item Tags"},
    )
    return llm


class OrganizationTagHelperTests(SimpleTestCase):
    def test_normalize_caps_and_dedupes(self):
        from api.messaging.organization_tags import normalize_tag_ids, parse_tag_ids_payload

        self.assertEqual(normalize_tag_ids([1, 1, 2, 3, 4]), [1, 2, 3])
        self.assertEqual(parse_tag_ids_payload(None), None)
        self.assertEqual(parse_tag_ids_payload([]), [])
        self.assertEqual(parse_tag_ids_payload("[5,6]"), [5, 6])

    def test_match_q_or_int_and_str(self):
        from api.messaging.organization_tags import tag_ids_match_q

        q = tag_ids_match_q("tag_ids", [12])
        children = q.children
        self.assertEqual(len(children), 2)


class OrganizationItemTagsTests(TestCase):
    def setUp(self):
        self.rag_chroma_patch = patch("api.rag.models.chroma_client", None)
        self.rag_chroma_patch.start()
        self.brief_patch = patch("api.rag.signals.async_generate_document_brief.delay")
        self.brief_patch.start()
        self.client = Client()
        llm = _bootstrap()
        self.owner = User.objects.create_user(username="org-tags-owner", password="x")
        self.member = User.objects.create_user(username="org-tags-member", password="x")
        self.org = Organization.objects.create(name="Org Tags Org", owner=self.owner)
        UserProfile.objects.filter(user=self.member).update(organization=self.org)
        self.member = User.objects.select_related("profile").get(pk=self.member.pk)
        self.tag_a = Tag.objects.create(title="Alpha", organization=self.org, enabled=True)
        self.tag_b = Tag.objects.create(title="Beta", organization=self.org, enabled=True)
        self.other_owner = User.objects.create_user(
            username="org-tags-other-owner", password="x"
        )
        self.other_org = Organization.objects.create(
            name="Other Tags Org", owner=self.other_owner
        )
        self.foreign_tag = Tag.objects.create(
            title="Foreign", organization=self.other_org, enabled=True
        )
        self.owner_token = Token.objects.create(user=self.owner, token_type="permanent")
        self.member_token = Token.objects.create(user=self.member, token_type="permanent")
        self.collection, _ = Collection.get_or_create_personal_collection(user=self.owner)
        self.owner_conv = Conversation.objects.create(
            user=self.owner, organization=self.org, title="Owner tags chat"
        )
        self.agent = Agent.objects.create(
            name="Tags Agent",
            salute="hi",
            act_as="helpful",
            user=self.owner,
            llm=llm,
            model_slug=llm.slug,
            model_provider="openai",
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

    def _doc(self, **kwargs):
        defaults = {
            "collection": self.collection,
            "created_by": self.owner,
            "text": "body",
            "name": "Doc",
            "brief": "brief",
            "total_tokens": 1,
            "visibility": Document.Visibility.ORGANIZATION,
            "organization": self.org,
        }
        defaults.update(kwargs)
        return Document.objects.create(**defaults)

    def _att(self, *, user=None, conversation=None, **kwargs):
        defaults = {
            "kind": "file",
            "file": ContentFile(b"x", name="a.png"),
            "content_type": "image/png",
            "visibility": MessageAttachment.Visibility.ORGANIZATION,
            "organization": self.org,
            "agent": self.agent,
        }
        defaults.update(kwargs)
        return MessageAttachment.objects.create(
            conversation=conversation or self.owner_conv,
            user=user or self.owner,
            **defaults,
        )

    def test_apply_tag_ids_rejects_foreign_and_caps(self):
        from api.messaging.organization_tags import apply_tag_ids

        doc = self._doc()
        with self.assertRaises(ValueError):
            apply_tag_ids(
                doc,
                organization_id=self.org.id,
                tag_ids=[self.foreign_tag.id],
                strict=True,
            )
        ordered = apply_tag_ids(
            doc,
            organization_id=self.org.id,
            tag_ids=[self.tag_a.id, self.tag_b.id, self.tag_a.id, 999999],
            strict=False,
        )
        self.assertEqual(ordered, [self.tag_a.id, self.tag_b.id])

    def test_json_contains_int_or_string(self):
        from api.messaging.organization_tags import tag_ids_match_q

        int_doc = self._doc(name="int-tags", tag_ids=[self.tag_a.id])
        str_doc = self._doc(name="str-tags", tag_ids=[str(self.tag_a.id)])
        other = self._doc(name="other-tags", tag_ids=[self.tag_b.id])
        matched = set(
            Document.objects.filter(
                tag_ids_match_q("tag_ids", [self.tag_a.id])
            ).values_list("id", flat=True)
        )
        self.assertIn(int_doc.id, matched)
        self.assertIn(str_doc.id, matched)
        self.assertNotIn(other.id, matched)

    def test_document_put_tag_ids_and_acl(self):
        personal = self._doc(
            name="secret tagged",
            visibility=Document.Visibility.PERSONAL,
            organization=None,
            tag_ids=[],
        )
        resp = self.client.put(
            f"/v1/rag/documents/{personal.id}/",
            data=json.dumps({"tag_ids": [self.tag_a.id]}),
            content_type="application/json",
            **self._auth(self.owner_token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("tag_ids"), [self.tag_a.id])
        personal.refresh_from_db()
        self.assertEqual(personal.tag_ids, [self.tag_a.id])

        forbidden = self.client.put(
            f"/v1/rag/documents/{personal.id}/",
            data=json.dumps({"tag_ids": [self.tag_b.id]}),
            content_type="application/json",
            **self._auth(self.member_token),
        )
        self.assertEqual(forbidden.status_code, 403)

        member_list = self.client.get(
            "/v1/rag/documents/",
            **self._auth(self.member_token),
        )
        self.assertEqual(member_list.status_code, 200)
        self.assertNotIn(personal.id, {d["id"] for d in member_list.json()})

    def test_gallery_patch_tags_without_visibility(self):
        att = self._att()
        resp = self.client.patch(
            f"/v1/messaging/gallery/{att.id}/",
            data=json.dumps({"tag_ids": [self.tag_a.id]}),
            content_type="application/json",
            **self._auth(self.owner_token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["item"]["tag_ids"], [self.tag_a.id])
        att.refresh_from_db()
        self.assertEqual(att.visibility, MessageAttachment.Visibility.ORGANIZATION)

        listed = self.client.get(
            f"/v1/messaging/gallery/?type=image&tag_id={self.tag_a.id}",
            **self._auth(self.owner_token),
        )
        self.assertEqual(listed.status_code, 200)
        ids = {item["id"] for item in listed.json()["results"]}
        self.assertIn(str(att.id), ids)

        member_forbidden = self.client.patch(
            f"/v1/messaging/gallery/{att.id}/",
            data=json.dumps({"tag_ids": [self.tag_b.id]}),
            content_type="application/json",
            **self._auth(self.member_token),
        )
        self.assertEqual(member_forbidden.status_code, 403)

    def test_list_tools_optional_tag_filter(self):
        from api.ai_layers.tools.list_attachments import _list_attachments_impl
        from api.ai_layers.tools.list_knowledge_base_documents import _list_impl

        tagged = self._doc(name="tagged policy", tag_ids=[self.tag_a.id])
        untagged = self._doc(name="plain policy", tag_ids=[])
        personal = self._doc(
            name="personal tagged",
            visibility=Document.Visibility.PERSONAL,
            organization=None,
            tag_ids=[self.tag_a.id],
        )

        all_docs = json.loads(_list_impl(user_id=self.member.id))
        all_ids = {d["id"] for d in all_docs["documents"]}
        self.assertIn(tagged.id, all_ids)
        self.assertIn(untagged.id, all_ids)
        self.assertNotIn(personal.id, all_ids)

        filtered = json.loads(
            _list_impl(user_id=self.member.id, tag_ids=[self.tag_a.id])
        )
        filtered_ids = {d["id"] for d in filtered["documents"]}
        self.assertEqual(filtered_ids, {tagged.id})

        att_tagged = self._att(tag_ids=[self.tag_a.id])
        att_plain = self._att(tag_ids=[])
        listed = _list_attachments_impl(
            kind="image",
            user_id=self.member.id,
        )
        listed_ids = {item.attachment_id for item in listed.attachments}
        self.assertIn(str(att_tagged.id), listed_ids)
        self.assertIn(str(att_plain.id), listed_ids)

        tagged_only = _list_attachments_impl(
            kind="image",
            user_id=self.member.id,
            tag_ids=[self.tag_a.id],
        )
        self.assertEqual(
            {item.attachment_id for item in tagged_only.attachments},
            {str(att_tagged.id)},
        )

    def test_get_tag_context_includes_and_dedup(self):
        from api.ai_layers.tools.get_tag_context import _get_tag_context_impl

        current = Conversation.objects.create(
            user=self.owner, organization=self.org, title="Current"
        )
        other = Conversation.objects.create(
            user=self.owner,
            organization=self.org,
            title="Other tagged",
            tags=[self.tag_a.id],
        )
        doc = self._doc(name="KB tagged", tag_ids=[self.tag_a.id])
        pointer = MessageAttachment.objects.create(
            conversation=self.owner_conv,
            user=self.owner,
            kind="rag_document",
            rag_document=doc,
            content_type="application/rag_document",
            visibility=MessageAttachment.Visibility.ORGANIZATION,
            organization=self.org,
            tag_ids=[self.tag_a.id],
        )
        gallery_file = self._att(tag_ids=[self.tag_a.id])

        default = _get_tag_context_impl(
            tag_id=self.tag_a.id,
            user_id=self.owner.id,
            organization_id=self.org.id,
            current_conversation_id=str(current.id),
        )
        self.assertEqual({c.conversation_id for c in default.conversations}, {str(other.id)})
        self.assertEqual({d.id for d in default.documents}, {doc.id})
        gallery_ids = {g.attachment_id for g in default.gallery}
        self.assertIn(str(gallery_file.id), gallery_ids)
        self.assertNotIn(str(pointer.id), gallery_ids)

        docs_only = _get_tag_context_impl(
            tag_id=self.tag_a.id,
            user_id=self.owner.id,
            organization_id=self.org.id,
            current_conversation_id=str(current.id),
            includes=["knowledge_base_documents"],
        )
        self.assertEqual(docs_only.conversations, [])
        self.assertEqual({d.id for d in docs_only.documents}, {doc.id})
        self.assertEqual(docs_only.gallery, [])

    def test_dependent_tools_inject_with_change_conversation_tags(self):
        from api.ai_layers.tools import (
            DEPENDENT_TOOL_REQUIREMENTS,
            list_available_tools,
            list_registered_tools,
            resolve_tools,
        )

        self.assertEqual(
            DEPENDENT_TOOL_REQUIREMENTS["change_document_tags"],
            ("change_conversation_tags",),
        )
        self.assertEqual(
            DEPENDENT_TOOL_REQUIREMENTS["change_attachment_tags"],
            ("change_conversation_tags",),
        )
        available = list_available_tools()
        self.assertIn("change_conversation_tags", available)
        self.assertNotIn("change_document_tags", available)
        self.assertNotIn("change_attachment_tags", available)
        registered = list_registered_tools()
        self.assertIn("change_document_tags", registered)
        self.assertIn("change_attachment_tags", registered)

        names = {
            t["name"]
            for t in resolve_tools(
                ["change_conversation_tags"],
                conversation_id=str(self.owner_conv.id),
                organization_id=self.org.id,
                user_id=self.owner.id,
            )
        }
        self.assertIn("change_conversation_tags", names)
        self.assertIn("change_document_tags", names)
        self.assertIn("change_attachment_tags", names)

        anonymous = {
            t["name"]
            for t in resolve_tools(
                ["change_conversation_tags"],
                conversation_id=str(self.owner_conv.id),
                organization_id=self.org.id,
            )
        }
        self.assertIn("change_conversation_tags", anonymous)
        self.assertNotIn("change_document_tags", anonymous)
        self.assertNotIn("change_attachment_tags", anonymous)
