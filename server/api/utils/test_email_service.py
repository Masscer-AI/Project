from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from api.utils.email_service import EmailService


class EmailServiceTests(SimpleTestCase):
    @patch("api.utils.email_service.requests.post")
    def test_send_email_includes_attachments_in_payload(self, mock_post):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"id": "email-123"}
        mock_post.return_value = mock_response

        service = EmailService(api_key="re_test_key")
        service.send_email(
            to="user@example.com",
            html="<p>Hello</p>",
            subject="Test",
            attachments=[
                {"filename": "report.docx", "content": "YmFzZTY0"},
            ],
        )

        mock_post.assert_called_once()
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(
            payload["attachments"],
            [{"filename": "report.docx", "content": "YmFzZTY0"}],
        )
        self.assertNotIn("attachments", payload.keys() - {"from", "to", "subject", "html", "attachments"})

    @patch("api.utils.email_service.requests.post")
    def test_send_email_omits_attachments_when_empty(self, mock_post):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"id": "email-123"}
        mock_post.return_value = mock_response

        service = EmailService(api_key="re_test_key")
        service.send_email(
            to="user@example.com",
            html="<p>Hello</p>",
            subject="Test",
            attachments=None,
        )

        payload = mock_post.call_args.kwargs["json"]
        self.assertNotIn("attachments", payload)
