from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import TestCase

from api.ai_layers.models import LanguageModel
from api.ai_layers.tasks import _extract_referenced_attachments_from_text
from api.authenticate.models import Organization, UserProfile
from api.consumption.models import Currency
from api.messaging.models import Conversation, MessageAttachment
from api.providers.models import AIProvider


def _bootstrap():
    Currency.objects.get_or_create(
        name="Compute Unit", defaults={"one_usd_is": 1000}
    )
    provider, _ = AIProvider.objects.get_or_create(name="OpenAI-ref-att")
    LanguageModel.objects.get_or_create(
        slug="gpt-ref-att",
        defaults={"provider": provider, "name": "GPT Ref Att"},
    )


class ReferencedAttachmentsTests(TestCase):
    def setUp(self):
        _bootstrap()
        self.owner = User.objects.create_user(username="ref-owner", password="x")
        self.member = User.objects.create_user(username="ref-member", password="x")
        self.org = Organization.objects.create(name="Ref Org", owner=self.owner)
        UserProfile.objects.filter(user=self.member).update(organization=self.org)
        self.owner_conv = Conversation.objects.create(
            user=self.owner, organization=self.org, title="Where the file was made"
        )
        self.member_conv = Conversation.objects.create(
            user=self.member, organization=self.org, title="Where it is shared"
        )

    def _att(self, conversation, user, visibility):
        return MessageAttachment.objects.create(
            conversation=conversation,
            user=user,
            organization=self.org,
            kind="file",
            file=ContentFile(b"pdf", name="report.pdf"),
            content_type="application/pdf",
            visibility=visibility,
        )

    def _resolve(self, att, conversation, user_id):
        text = f"[Report](attachment:{att.id})"
        return _extract_referenced_attachments_from_text(
            text, conversation_id=str(conversation.id), user_id=user_id
        )

    def test_resolves_org_file_from_another_conversation(self):
        att = self._att(self.owner_conv, self.owner, MessageAttachment.Visibility.ORGANIZATION)
        resolved = self._resolve(att, self.member_conv, self.member.id)
        self.assertEqual([r["attachment_id"] for r in resolved], [str(att.id)])

    def test_skips_personal_file_of_another_user(self):
        att = self._att(self.owner_conv, self.owner, MessageAttachment.Visibility.PERSONAL)
        self.assertEqual(self._resolve(att, self.member_conv, self.member.id), [])

    def test_anonymous_resolves_only_current_conversation(self):
        att = self._att(self.owner_conv, self.owner, MessageAttachment.Visibility.ORGANIZATION)
        self.assertEqual(self._resolve(att, self.member_conv, None), [])
        resolved = self._resolve(att, self.owner_conv, None)
        self.assertEqual([r["attachment_id"] for r in resolved], [str(att.id)])
