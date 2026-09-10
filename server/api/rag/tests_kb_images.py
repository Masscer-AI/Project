import base64
import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from api.ai_layers.models import LanguageModel
from api.authenticate.models import Organization, Token
from api.consumption.models import Currency
from api.messaging.models import Conversation, MessageAttachment
from api.providers.models import AIProvider
from api.rag.actions import extract_image_text, infer_upload_format
from api.rag.models import Document
from api.rag.views import KB_FROM_ATTACHMENT_METADATA_KEY

MINIMAL_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+X4dIAAAAASUVORK5CYII="
)


def _ensure_user_bootstrap():
    Currency.objects.get_or_create(
        name="Compute Unit", defaults={"one_usd_is": 1000}
    )
    provider, _ = AIProvider.objects.get_or_create(name="OpenAI")
    LanguageModel.objects.get_or_create(
        slug="test-llm-kb-images",
        defaults={"provider": provider, "name": "Test LLM KB Images"},
    )


class InferUploadFormatImageTests(TestCase):
    def test_png_extension_and_magic(self):
        named = SimpleUploadedFile("photo.png", MINIMAL_PNG_BYTES, content_type="")
        self.assertEqual(infer_upload_format(named), "image")

        anonymous = SimpleUploadedFile(
            "blob", MINIMAL_PNG_BYTES, content_type="application/octet-stream"
        )
        self.assertEqual(infer_upload_format(anonymous), "image")

    def test_jpeg_magic_is_image_not_txt(self):
        jpeg = SimpleUploadedFile(
            "blob",
            b"\xff\xd8\xff\xe0" + b"\x00" * 16,
            content_type="application/octet-stream",
        )
        self.assertEqual(infer_upload_format(jpeg), "image")

    def test_unsupported_image_mime_raises(self):
        bmp = SimpleUploadedFile(
            "x.bmp", b"BM" + b"\x00" * 16, content_type="image/bmp"
        )
        with self.assertRaises(ValueError):
            infer_upload_format(bmp)


class ExtractImageTextTests(TestCase):
    @patch("api.rag.actions.OpenAI")
    def test_uses_gpt_5_6_terra(self, openai_cls):
        client = openai_cls.return_value
        client.responses.create.return_value.output_text = "A red square"
        text = extract_image_text(
            MINIMAL_PNG_BYTES, content_type="image/png", filename="a.png"
        )
        self.assertEqual(text, "A red square")
        kwargs = client.responses.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "gpt-5.6-terra")
        content = kwargs["input"][0]["content"]
        self.assertEqual(content[1]["type"], "input_image")
        self.assertTrue(content[1]["image_url"].startswith("data:image/png;base64,"))

    @patch("api.rag.actions.OpenAI")
    def test_empty_output_raises(self, openai_cls):
        client = openai_cls.return_value
        client.responses.create.return_value.output_text = "  "
        client.responses.create.return_value.output = []
        with self.assertRaises(ValueError):
            extract_image_text(MINIMAL_PNG_BYTES, content_type="image/png")


class KnowledgeBaseImageUploadTests(TestCase):
    def setUp(self):
        self.rag_chroma_patch = patch("api.rag.models.chroma_client", None)
        self.rag_chroma_patch.start()
        self.brief_patch = patch("api.rag.signals.async_generate_document_brief.delay")
        self.brief_patch.start()
        self.ff_patch = patch(
            "api.authenticate.services.FeatureFlagService.is_feature_enabled",
            return_value=(True, "test"),
        )
        self.ff_patch.start()
        self.client = Client()
        _ensure_user_bootstrap()
        self.owner = User.objects.create_user(username="kb-img-owner", password="x")
        self.org = Organization.objects.create(name="KB Img Org", owner=self.owner)
        self.token = Token.objects.create(user=self.owner, token_type="permanent")

    def tearDown(self):
        self.ff_patch.stop()
        self.brief_patch.stop()
        self.rag_chroma_patch.stop()

    def _auth(self):
        return {"HTTP_AUTHORIZATION": f"Token {self.token.key}"}

    @patch("api.rag.actions.extract_image_text", return_value="Caption of a cat")
    def test_png_upload_indexes_extracted_text(self, _extract):
        png = SimpleUploadedFile(
            "cat.png", MINIMAL_PNG_BYTES, content_type="image/png"
        )
        resp = self.client.post(
            "/v1/rag/documents/",
            {"file": png, "source": "knowledge_base", "visibility": "personal"},
            **self._auth(),
        )
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body["text"], "Caption of a cat")
        self.assertEqual(body["content_type"], "image/png")
        doc = Document.objects.get(pk=body["id"])
        self.assertEqual(doc.text, "Caption of a cat")
        self.assertEqual(doc.content_type, "image/png")

    @patch(
        "api.rag.actions.extract_image_text",
        side_effect=ValueError("Failed to extract text from image: boom"),
    )
    def test_png_upload_failure_creates_no_document(self, _extract):
        png = SimpleUploadedFile(
            "cat.png", MINIMAL_PNG_BYTES, content_type="image/png"
        )
        resp = self.client.post(
            "/v1/rag/documents/",
            {"file": png, "source": "knowledge_base", "visibility": "personal"},
            **self._auth(),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Document.objects.count(), 0)
        self.assertIn("Failed to extract text from image", resp.json()["error"])


class DocumentFromAttachmentTests(TestCase):
    def setUp(self):
        self.rag_chroma_patch = patch("api.rag.models.chroma_client", None)
        self.rag_chroma_patch.start()
        self.brief_patch = patch("api.rag.signals.async_generate_document_brief.delay")
        self.brief_patch.start()
        self.ff_patch = patch(
            "api.authenticate.services.FeatureFlagService.is_feature_enabled",
            return_value=(True, "test"),
        )
        self.ff_patch.start()
        self.client = Client()
        _ensure_user_bootstrap()
        self.owner = User.objects.create_user(username="kb-att-owner", password="x")
        self.other = User.objects.create_user(username="kb-att-other", password="x")
        self.org = Organization.objects.create(name="KB Att Org", owner=self.owner)
        self.owner_token = Token.objects.create(user=self.owner, token_type="permanent")
        self.other_token = Token.objects.create(user=self.other, token_type="permanent")
        self.conversation = Conversation.objects.create(user=self.owner)
        self.other_conversation = Conversation.objects.create(user=self.other)

    def tearDown(self):
        self.ff_patch.stop()
        self.brief_patch.stop()
        self.rag_chroma_patch.stop()

    def _auth(self, token=None):
        token = token or self.owner_token
        return {"HTTP_AUTHORIZATION": f"Token {token.key}"}

    def _post(self, attachment_id, token=None):
        return self.client.post(
            "/v1/rag/documents/from-attachment/",
            data=json.dumps({"attachment_id": str(attachment_id)}),
            content_type="application/json",
            **self._auth(token),
        )

    @patch("api.rag.actions.extract_image_text", return_value="Indexed image text")
    def test_image_attachment_creates_document(self, _extract):
        att = MessageAttachment.objects.create(
            conversation=self.conversation,
            user=self.owner,
            kind="file",
            file=ContentFile(MINIMAL_PNG_BYTES, name="gen.png"),
            content_type="image/png",
            visibility=MessageAttachment.Visibility.PERSONAL,
        )
        resp = self._post(att.id)
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body["text"], "Indexed image text")
        self.assertEqual(body["visibility"], Document.Visibility.PERSONAL)
        att.refresh_from_db()
        self.assertEqual(att.metadata[KB_FROM_ATTACHMENT_METADATA_KEY], body["id"])

    def test_text_document_attachment(self):
        att = MessageAttachment.objects.create(
            conversation=self.conversation,
            user=self.owner,
            kind="file",
            file=ContentFile(b"Hello knowledge base", name="notes.txt"),
            content_type="text/plain",
            visibility=MessageAttachment.Visibility.ORGANIZATION,
            organization=self.org,
        )
        resp = self._post(att.id)
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body["text"], "Hello knowledge base")
        self.assertEqual(body["visibility"], Document.Visibility.ORGANIZATION)

    def test_pdf_attachment(self):
        import fitz

        pdf = fitz.open()
        page = pdf.new_page()
        page.insert_text((72, 72), "PDF knowledge")
        raw = pdf.tobytes()
        pdf.close()
        att = MessageAttachment.objects.create(
            conversation=self.conversation,
            user=self.owner,
            kind="file",
            file=ContentFile(raw, name="doc.pdf"),
            content_type="application/pdf",
        )
        resp = self._post(att.id)
        self.assertEqual(resp.status_code, 201)
        self.assertIn("PDF knowledge", resp.json()["text"])

    def test_other_users_attachment_forbidden(self):
        att = MessageAttachment.objects.create(
            conversation=self.other_conversation,
            user=self.other,
            kind="file",
            file=ContentFile(b"secret notes", name="secret.txt"),
            content_type="text/plain",
        )
        resp = self._post(att.id)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(Document.objects.count(), 0)

    def test_video_rejected(self):
        att = MessageAttachment.objects.create(
            conversation=self.conversation,
            user=self.owner,
            kind="file",
            file=ContentFile(b"fake-video", name="clip.mp4"),
            content_type="video/mp4",
        )
        resp = self._post(att.id)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Video and audio", resp.json()["error"])
        self.assertEqual(Document.objects.count(), 0)

    @patch("api.rag.actions.extract_image_text", return_value="same caption")
    def test_second_call_is_idempotent(self, _extract):
        att = MessageAttachment.objects.create(
            conversation=self.conversation,
            user=self.owner,
            kind="file",
            file=ContentFile(MINIMAL_PNG_BYTES, name="once.png"),
            content_type="image/png",
        )
        first = self._post(att.id)
        self.assertEqual(first.status_code, 201)
        second = self._post(att.id)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json().get("already_indexed"))
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(Document.objects.count(), 1)

    def test_link_visibility_maps_to_personal(self):
        att = MessageAttachment.objects.create(
            conversation=self.conversation,
            user=self.owner,
            kind="file",
            file=ContentFile(b"linkable notes", name="public.txt"),
            content_type="text/plain",
            visibility=MessageAttachment.Visibility.LINK,
            organization=self.org,
        )
        resp = self._post(att.id)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["visibility"], Document.Visibility.PERSONAL)
        doc = Document.objects.get(pk=resp.json()["id"])
        self.assertIsNone(doc.organization_id)
