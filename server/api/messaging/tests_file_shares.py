from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.utils import timezone

from api.ai_layers.models import LanguageModel
from api.ai_layers.tools.create_file_share import _create_file_share_impl
from api.authenticate.models import Organization
from api.consumption.models import Currency
from api.messaging.file_shares import create_file_share
from api.messaging.models import (
    Conversation,
    FileShare,
    MessageAttachment,
    SharedConversation,
)
from api.providers.models import AIProvider


def _bootstrap():
    Currency.objects.get_or_create(
        name="Compute Unit", defaults={"one_usd_is": 1000}
    )
    provider, _ = AIProvider.objects.get_or_create(name="OpenAI-file-share")
    LanguageModel.objects.get_or_create(
        slug="gpt-file-share",
        defaults={"provider": provider, "name": "GPT File Share"},
    )


@override_settings(FRONTEND_URL="https://app.example.com")
class FileShareTests(TestCase):
    def setUp(self):
        _bootstrap()
        self.owner = User.objects.create_user(username="fs-owner", password="x")
        self.outsider = User.objects.create_user(username="fs-out", password="x")
        self.org = Organization.objects.create(name="FS Org", owner=self.owner)
        self.conv = Conversation.objects.create(
            user=self.owner, organization=self.org, title="Owner chat"
        )
        self.outsider_conv = Conversation.objects.create(
            user=self.outsider, title="Outsider chat"
        )
        self.report = self._att(self.conv, self.owner, "report.pdf", b"pdf-bytes")
        self.sheet = self._att(self.conv, self.owner, "sheet.xlsx", b"xlsx-bytes")

    def _att(self, conversation, user, name, content):
        return MessageAttachment.objects.create(
            conversation=conversation,
            user=user,
            kind="file",
            file=ContentFile(content, name=name),
            content_type="application/octet-stream",
            metadata={"name": name},
        )

    def _share(self, **kwargs):
        return create_file_share(
            user=self.owner,
            attachment_ids=[str(self.report.id), str(self.sheet.id)],
            **kwargs,
        )

    def test_tool_creates_share_with_link_and_default_expiry(self):
        result = _create_file_share_impl(
            attachment_ids=[str(self.report.id), str(self.sheet.id)],
            expires_in_days=7,
            max_downloads=None,
            user_id=self.owner.id,
            conversation_id=str(self.conv.id),
        )
        share = FileShare.objects.get(id=result.share_id)
        self.assertEqual(result.url, f"https://app.example.com/d/{share.id}")
        self.assertEqual(share.attachments.count(), 2)
        self.assertEqual(share.organization, self.org)
        self.assertAlmostEqual(
            share.expires_at,
            timezone.now() + timedelta(days=7),
            delta=timedelta(minutes=1),
        )
        self.assertEqual(
            [f.name for f in result.files], ["report.pdf", "sheet.xlsx"]
        )

    def test_rejects_attachment_user_cannot_access(self):
        other = self._att(self.outsider_conv, self.outsider, "secret.pdf", b"s")
        with self.assertRaisesMessage(ValueError, "not available to you"):
            create_file_share(user=self.owner, attachment_ids=[str(other.id)])
        self.assertFalse(FileShare.objects.exists())

    def test_rejects_unknown_attachment(self):
        missing = "11111111-1111-4111-8111-111111111111"
        with self.assertRaisesMessage(ValueError, "Attachments not found"):
            create_file_share(user=self.owner, attachment_ids=[missing])

    def test_detail_lists_files_when_active(self):
        share = self._share()
        res = self.client.get(f"/v1/messaging/file-shares/{share.id}/")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "active")
        self.assertEqual(body["organization_name"], "FS Org")
        self.assertEqual(
            [f["name"] for f in body["files"]], ["report.pdf", "sheet.xlsx"]
        )

    def test_detail_hides_files_when_expired(self):
        share = self._share()
        FileShare.objects.filter(id=share.id).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        body = self.client.get(f"/v1/messaging/file-shares/{share.id}/").json()
        self.assertEqual(body["status"], "expired")
        self.assertEqual(body["files"], [])

    def test_download_streams_file_and_counts(self):
        share = self._share()
        res = self.client.get(
            f"/v1/messaging/file-shares/{share.id}/files/{self.report.id}/"
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn('attachment; filename="report.pdf"', res["Content-Disposition"])
        self.assertEqual(b"".join(res.streaming_content), b"pdf-bytes")
        share.refresh_from_db()
        self.assertEqual(share.download_count, 1)

    def test_download_limit_is_enforced(self):
        share = self._share(max_downloads=1)
        url = f"/v1/messaging/file-shares/{share.id}/files/{self.report.id}/"
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 410)
        body = self.client.get(f"/v1/messaging/file-shares/{share.id}/").json()
        self.assertEqual(body["status"], "limit_reached")

    def test_download_refused_when_expired(self):
        share = self._share()
        FileShare.objects.filter(id=share.id).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        res = self.client.get(
            f"/v1/messaging/file-shares/{share.id}/files/{self.report.id}/"
        )
        self.assertEqual(res.status_code, 410)

    def test_download_refuses_file_outside_share(self):
        share = create_file_share(
            user=self.owner, attachment_ids=[str(self.report.id)]
        )
        res = self.client.get(
            f"/v1/messaging/file-shares/{share.id}/files/{self.sheet.id}/"
        )
        self.assertEqual(res.status_code, 404)


class SharedConversationExpiryTests(TestCase):
    def setUp(self):
        _bootstrap()
        self.owner = User.objects.create_user(username="sc-owner", password="x")
        self.conv = Conversation.objects.create(user=self.owner, title="Shared chat")

    def test_expired_share_is_not_found(self):
        share = SharedConversation.objects.create(
            conversation=self.conv,
            user=self.owner,
            valid_until=timezone.now() - timedelta(minutes=1),
        )
        res = self.client.get(f"/v1/messaging/shared-conversations/{share.id}/")
        self.assertEqual(res.status_code, 404)

    def test_active_share_loads(self):
        share = SharedConversation.objects.create(
            conversation=self.conv,
            user=self.owner,
            valid_until=timezone.now() + timedelta(days=1),
        )
        res = self.client.get(f"/v1/messaging/shared-conversations/{share.id}/")
        self.assertEqual(res.status_code, 200)
