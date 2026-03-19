import os
from typing import Iterable

import requests


class EmailService:
    """Simple Resend email client for backend usage."""

    BASE_URL = "https://api.resend.com/emails"
    DEFAULT_FROM_EMAIL = "no-reply@appcot.masscer.ai"

    def __init__(self, api_key: str | None = None, timeout_seconds: int = 20):
        self.api_key = api_key or os.environ.get("RESEND_API_KEY", "")
        self.timeout_seconds = timeout_seconds

        if not self.api_key:
            raise ValueError("RESEND_API_KEY is not configured")

    def send_email(
        self,
        to: str | Iterable[str],
        html: str,
        subject: str,
        from_email: str | None = None,
        from_name: str | None = None,
    ) -> dict:
        """
        Send an email with Resend.

        Args:
            to: recipient email or iterable of recipients.
            html: html body content.
            subject: email subject.
            from_email: sender email (defaults to no-reply@appcot.masscer.ai).
            from_name: optional sender display name, e.g. "Masscer".
        """
        recipients = [to] if isinstance(to, str) else list(to)
        if not recipients:
            raise ValueError("'to' must contain at least one recipient")
        if not html:
            raise ValueError("'html' cannot be empty")
        if not subject:
            raise ValueError("'subject' cannot be empty")

        sender_email = from_email or self.DEFAULT_FROM_EMAIL
        sender = f"{from_name} <{sender_email}>" if from_name else sender_email

        payload = {
            "from": sender,
            "to": recipients,
            "subject": subject,
            "html": html,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            self.BASE_URL,
            headers=headers,
            json=payload,
            timeout=self.timeout_seconds,
        )

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            details = ""
            try:
                details = response.text
            except Exception:
                details = "<unable to read response body>"
            raise RuntimeError(f"Resend send_email failed: {details}") from exc

        return response.json()
