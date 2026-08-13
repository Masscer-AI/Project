from datetime import date

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import TestCase

from api.ai_layers.models import LanguageModel
from api.ai_layers.tools.list_attachments import _list_attachments_impl
from api.authenticate.models import Organization, Role, RoleAssignment, UserProfile
from api.consumption.models import Currency
from api.messaging.attachment_access import (
    apply_attachment_ownership,
    attachments_visible_q,
    user_can_access_attachment,
    user_can_manage_attachment,
)
from api.messaging.models import Conversation, MessageAttachment
from api.providers.models import AIProvider


def _bootstrap():
    Currency.objects.get_or_create(
        name="Compute Unit", defaults={"one_usd_is": 1000}
    )
    provider, _ = AIProvider.objects.get_or_create(name="OpenAI-att-acl")
    LanguageModel.objects.get_or_create(
        slug="gpt-att-acl",
        defaults={"provider": provider, "name": "GPT Att ACL"},
    )


class AttachmentVisibilityAclTests(TestCase):
    def setUp(self):
        _bootstrap()
        self.owner = User.objects.create_user(username="att-acl-owner", password="x")
        self.member = User.objects.create_user(username="att-acl-member", password="x")
        self.outsider = User.objects.create_user(username="att-acl-out", password="x")
        self.org = Organization.objects.create(name="Att ACL Org", owner=self.owner)
        UserProfile.objects.filter(user=self.member).update(organization=self.org)
        self.member = User.objects.select_related("profile").get(pk=self.member.pk)
        self.role = Role.objects.create(organization=self.org, name="Analysts")
        RoleAssignment.objects.create(
            user=self.member,
            organization=self.org,
            role=self.role,
            from_date=date.today(),
        )
        self.owner_conv = Conversation.objects.create(
            user=self.owner, organization=self.org, title="Owner chat"
        )
        self.member_conv = Conversation.objects.create(
            user=self.member, organization=self.org, title="Member chat"
        )
        self.outsider_conv = Conversation.objects.create(
            user=self.outsider, title="Outsider chat"
        )

    def _file(self, name="a.png", content=b"x"):
        return ContentFile(content, name=name)

    def _att(self, *, conversation, user, **kwargs):
        defaults = {
            "kind": "file",
            "file": self._file(),
            "content_type": "image/png",
            "visibility": MessageAttachment.Visibility.PERSONAL,
        }
        defaults.update(kwargs)
        return MessageAttachment.objects.create(
            conversation=conversation, user=user, **defaults
        )

    def test_personal_hidden_from_other_org_members(self):
        att = self._att(conversation=self.owner_conv, user=self.owner)
        self.assertTrue(
            user_can_access_attachment(att, user=self.owner)
        )
        self.assertFalse(
            user_can_access_attachment(att, user=self.member)
        )
        self.assertFalse(
            user_can_access_attachment(att, user=self.outsider)
        )

    def test_current_conversation_is_always_visible(self):
        att = self._att(conversation=self.owner_conv, user=self.owner)
        self.assertTrue(
            user_can_access_attachment(
                att,
                user=self.member,
                conversation_id=str(self.owner_conv.id),
            )
        )

    def test_organization_visibility_lists_to_members(self):
        att = self._att(conversation=self.owner_conv, user=self.owner)
        apply_attachment_ownership(
            att, user=self.owner, visibility="organization"
        )
        att.refresh_from_db()
        self.assertEqual(att.visibility, "organization")
        self.assertEqual(att.organization_id, self.org.id)
        self.assertTrue(user_can_access_attachment(att, user=self.member))
        self.assertFalse(user_can_access_attachment(att, user=self.outsider))

        listed = _list_attachments_impl(
            kind="image",
            user_id=self.member.id,
            conversation_id=str(self.member_conv.id),
        )
        ids = {item.attachment_id for item in listed.attachments}
        self.assertIn(str(att.id), ids)

    def test_link_visibility_lists_to_org_members(self):
        att = self._att(conversation=self.owner_conv, user=self.owner)
        apply_attachment_ownership(att, user=self.owner, visibility="link")
        att.refresh_from_db()
        self.assertEqual(att.visibility, "link")
        self.assertTrue(user_can_access_attachment(att, user=self.member))
        self.assertFalse(user_can_access_attachment(att, user=self.outsider))

    def test_roles_visibility(self):
        att = self._att(conversation=self.owner_conv, user=self.owner)
        apply_attachment_ownership(
            att,
            user=self.owner,
            visibility="roles",
            role_ids=[str(self.role.id)],
        )
        other_role = Role.objects.create(organization=self.org, name="Managers")
        outsider_member = User.objects.create_user(
            username="att-acl-no-role", password="x"
        )
        UserProfile.objects.filter(user=outsider_member).update(
            organization=self.org
        )
        outsider_member = User.objects.select_related("profile").get(
            pk=outsider_member.pk
        )
        RoleAssignment.objects.create(
            user=outsider_member,
            organization=self.org,
            role=other_role,
            from_date=date.today(),
        )
        self.assertTrue(user_can_access_attachment(att, user=self.member))
        self.assertTrue(user_can_access_attachment(att, user=self.owner))
        self.assertFalse(user_can_access_attachment(att, user=outsider_member))

    def test_conversation_owner_and_org_owner_can_manage(self):
        att = self._att(conversation=self.member_conv, user=self.member)
        self.assertTrue(user_can_manage_attachment(att, self.member))
        self.assertTrue(user_can_manage_attachment(att, self.owner))
        self.assertFalse(user_can_manage_attachment(att, self.outsider))

    def test_update_attachment_visibility_tool_shares_with_org(self):
        from api.ai_layers.tools.update_attachment_visibility import (
            _update_attachment_visibility_impl,
        )

        att = self._att(conversation=self.owner_conv, user=self.owner)
        result = _update_attachment_visibility_impl(
            attachment_id=str(att.id),
            visibility="organization",
            role_ids=None,
            user_id=self.owner.id,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.visibility, "organization")
        att.refresh_from_db()
        self.assertEqual(att.visibility, "organization")
        self.assertEqual(att.organization_id, self.org.id)
        self.assertTrue(user_can_access_attachment(att, user=self.member))

        listed = _list_attachments_impl(
            kind="image",
            user_id=self.member.id,
            conversation_id=str(self.member_conv.id),
        )
        ids = {item.attachment_id for item in listed.attachments}
        self.assertIn(str(att.id), ids)

    def test_update_attachment_visibility_tool_forbidden_for_member(self):
        from api.ai_layers.tools.update_attachment_visibility import (
            _update_attachment_visibility_impl,
        )

        att = self._att(conversation=self.owner_conv, user=self.owner)
        with self.assertRaises(ValueError) as ctx:
            _update_attachment_visibility_impl(
                attachment_id=str(att.id),
                visibility="organization",
                role_ids=None,
                user_id=self.member.id,
            )
        self.assertIn("cannot change visibility", str(ctx.exception))
        att.refresh_from_db()
        self.assertEqual(att.visibility, "personal")

    def test_update_attachment_visibility_tool_is_registered(self):
        from api.ai_layers.tools import USER_REQUIRED_TOOL_NAMES, list_available_tools

        self.assertIn("update_attachment_visibility", list_available_tools())
        self.assertIn("update_attachment_visibility", USER_REQUIRED_TOOL_NAMES)

    def test_member_cannot_apply_ownership_on_others_file(self):
        att = self._att(conversation=self.owner_conv, user=self.owner)
        self.assertFalse(user_can_manage_attachment(att, self.member))

    def test_visible_q_anonymous_is_conversation_only(self):
        mine = self._att(conversation=self.owner_conv, user=self.owner)
        other = self._att(conversation=self.member_conv, user=self.member)
        qs = MessageAttachment.objects.filter(
            attachments_visible_q(conversation_id=str(self.owner_conv.id))
        )
        ids = set(qs.values_list("id", flat=True))
        self.assertIn(mine.id, ids)
        self.assertNotIn(other.id, ids)
