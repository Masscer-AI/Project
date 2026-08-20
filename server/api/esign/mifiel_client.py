"""
Thin HTTP client for the Mifiel e-signature API (https://docs.mifiel.com/es/).

Deliberately not using Mifiel's official SDKs to keep this dependency-light —
just `requests` (already a project dependency) plus Basic Auth.
"""

from __future__ import annotations

import base64
from typing import Literal

import requests
from django.conf import settings


class MifielAPIError(Exception):
    """Raised on any non-2xx response from the Mifiel API."""

    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"Mifiel API error ({status_code}): {body}")


class MifielClient:
    def __init__(
        self,
        *,
        app_id: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int = 30,
    ):
        self.app_id = app_id or settings.MIFIEL_APP_ID
        self.api_key = api_key or settings.MIFIEL_API_KEY
        self.base_url = (base_url or settings.MIFIEL_BASE_URL).rstrip("/")
        self.timeout = timeout
        if not self.app_id or not self.api_key:
            raise MifielAPIError(
                0, "MIFIEL_APP_ID / MIFIEL_API_KEY are not configured on this server."
            )

    def _auth_header(self) -> dict[str, str]:
        raw = f"{self.app_id}:{self.api_key}".encode("utf-8")
        return {"Authorization": f"Basic {base64.b64encode(raw).decode('ascii')}"}

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}{path}"
        headers = {**self._auth_header(), **kwargs.pop("headers", {})}
        response = requests.request(
            method, url, headers=headers, timeout=self.timeout, **kwargs
        )
        if not response.ok:
            raise MifielAPIError(response.status_code, response.text)
        return response

    def create_document(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        signatories: list[dict],
        external_id: str,
        send_invites: bool = True,
        days_to_expire: int | None = None,
    ) -> dict:
        """POST /documents — upload a PDF and register its signatories."""
        files = {"file": (filename, file_bytes, "application/pdf")}
        data: dict = {
            "external_id": external_id,
            "send_invites": str(send_invites).lower(),
        }
        for i, signer in enumerate(signatories):
            for key, value in signer.items():
                if value:
                    data[f"signatories[{i}][{key}]"] = value
        if days_to_expire is not None:
            data["days_to_expire"] = str(days_to_expire)
        response = self._request("POST", "/documents", files=files, data=data)
        return response.json()

    def get_document(self, document_id: str) -> dict:
        """GET /documents/{id} — current state of a document."""
        response = self._request("GET", f"/documents/{document_id}")
        return response.json()

    def download_signed_file(
        self,
        document_id: str,
        file_type: Literal["file_signed", "file_signed_xml"],
    ) -> bytes:
        """Download the signed PDF or the legally-binding XML (with NOM-151 record)."""
        response = self._request("GET", f"/documents/{document_id}/{file_type}")
        return response.content

    def list_webhooks(self) -> list[dict]:
        """GET /api/v1/webhooks — currently registered webhooks for this account."""
        response = self._request("GET", "/webhooks")
        return response.json()

    def register_webhook(self, *, url: str, callback_type: str) -> dict:
        """
        POST /api/v1/webhooks — one-time setup call, not invoked per signature
        request. callback_type: document_closed | signer_completed |
        signer_rejected | document_deleted.
        """
        response = self._request(
            "POST", "/webhooks", json={"url": url, "callback_type": callback_type}
        )
        return response.json()
