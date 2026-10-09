from __future__ import annotations

import base64
import time

import requests
from django.conf import settings

SIGNATURE_BOX = {"x": 72, "y": 700, "w": 180, "h": 60, "page": 1}
_LINE_STEP = 70
_TOKEN_SKEW_SECONDS = 30


class JaakAPIError(Exception):
    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"Jaak API error ({status_code}): {body}")


class JaakClient:
    _token = ""
    _token_until = 0.0

    def __init__(
        self,
        *,
        email: str | None = None,
        password: str | None = None,
        base_url: str | None = None,
        timeout: int = 60,
    ):
        self.email = email if email is not None else settings.JAAK_API_EMAIL
        self.password = password if password is not None else settings.JAAK_API_PASSWORD
        self.base_url = (base_url or settings.JAAK_API_BASE).rstrip("/")
        self.timeout = timeout
        if not self.email or not self.password:
            raise JaakAPIError(0, "JAAK_API_EMAIL / JAAK_API_PASSWORD are not configured")

    def _request(self, method: str, path: str, *, auth: bool = True, **kwargs) -> dict:
        headers = {"Accept": "application/json", **kwargs.pop("headers", {})}
        if auth:
            headers["Authorization"] = f"Bearer {self.access_token()}"
        response = requests.request(
            method,
            f"{self.base_url}{path}",
            headers=headers,
            timeout=self.timeout,
            **kwargs,
        )
        if not response.ok:
            raise JaakAPIError(response.status_code, response.text)
        if not response.content:
            return {}
        return response.json()

    def access_token(self) -> str:
        now = time.monotonic()
        if JaakClient._token and now < JaakClient._token_until - _TOKEN_SKEW_SECONDS:
            return JaakClient._token
        body = self._request(
            "POST",
            "/sign-in",
            auth=False,
            json={"email": self.email, "password": self.password},
        )
        token = str(body.get("accessToken") or "")
        if not token:
            raise JaakAPIError(200, "sign-in returned no accessToken")
        expires_in = int(body.get("expiresIn") or 900)
        JaakClient._token = token
        JaakClient._token_until = now + expires_in
        return token

    def create_template(self, *, name: str, filename: str, file_bytes: bytes, roles: list[str]) -> dict:
        fields = []
        for index, role in enumerate(roles):
            area = dict(SIGNATURE_BOX)
            area["y"] = SIGNATURE_BOX["y"] - index * _LINE_STEP
            fields.append(
                {
                    "name": f"Firma {index + 1}",
                    "type": "signature",
                    "required": True,
                    "role": role,
                    "areas": [area],
                }
            )
        return self._request(
            "POST",
            "/templates",
            json={
                "name": name[:255],
                "signature_type": "efirma_sat",
                "add_tsa_timestamp": False,
                "tsa_on_creation": True,
                "tsa_per_signer": True,
                "submitters": [{"name": role} for role in roles],
                "documents": [
                    {
                        "name": filename if filename.lower().endswith(".pdf") else f"{filename}.pdf",
                        "file": base64.b64encode(file_bytes).decode("ascii"),
                        "fields": fields,
                    }
                ],
            },
        )

    def create_submission(self, *, template_id: str, signers: list[dict]) -> dict:
        submitters = []
        for index, signer in enumerate(signers):
            submitters.append(
                {
                    "email": signer["email"],
                    "name": signer["name"],
                    "role": f"Firmante {index + 1}",
                    "send_email": True,
                    "send_sms": False,
                    "send_whatsapp": False,
                }
            )
        return self._request(
            "POST",
            "/submissions",
            json={
                "template_id": template_id,
                "send_email": True,
                "send_sms": False,
                "send_whatsapp": False,
                "submitters": submitters,
            },
        )
