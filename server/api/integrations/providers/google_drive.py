"""
Google Drive integration provider (OAuth + Drive API v3).
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

import requests

from .base import IntegrationProvider, IntegrationProviderError

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
GOOGLE_DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"

GOOGLE_EXPORT_MIME: dict[str, str] = {
    "application/vnd.google-apps.document": "text/plain",
    # Google Sheets export as CSV (text). Native .xlsx uploads use read_file_content.
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}

_IMPORTABLE_MIME_PREFIXES = (
    "application/vnd.google-apps.",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument",
    "text/",
)

DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
IDENTITY_SCOPES = "openid email profile"
ALL_SCOPES = f"{IDENTITY_SCOPES} {DRIVE_READONLY_SCOPE}"
_DEFAULT_TIMEOUT = 20


class GoogleDriveProvider(IntegrationProvider):
    provider_key = "google_drive"

    def get_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": ALL_SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    def exchange_code_for_token(self, code: str) -> dict[str, Any]:
        payload = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "code": code,
        }
        return self._post_token(payload)

    def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        payload = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
        }
        return self._post_token(payload)

    def _post_token(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = requests.post(GOOGLE_TOKEN_URL, data=payload, timeout=_DEFAULT_TIMEOUT)
            data = resp.json()
        except Exception as exc:
            raise IntegrationProviderError(f"Token request failed: {exc}") from exc

        if resp.status_code != 200 or "access_token" not in data:
            raise IntegrationProviderError(
                f"Token request failed: {data.get('error_description', data)}",
                status_code=resp.status_code,
                response_data=data if isinstance(data, dict) else {},
            )
        return data

    def fetch_account_info(self, access_token: str) -> dict[str, Any]:
        try:
            resp = requests.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=_DEFAULT_TIMEOUT,
            )
            data = resp.json()
        except Exception as exc:
            raise IntegrationProviderError(f"Userinfo request failed: {exc}") from exc

        if resp.status_code != 200:
            raise IntegrationProviderError(
                f"Userinfo request failed: {data}",
                status_code=resp.status_code,
                response_data=data if isinstance(data, dict) else {},
            )
        return data

    def list_files(self, access_token: str, *, limit: int = 20) -> list[dict[str, Any]]:
        params = {
            "pageSize": min(max(limit, 1), 100),
            "fields": "files(id,name,mimeType,modifiedTime)",
            "orderBy": "modifiedTime desc",
        }
        try:
            resp = requests.get(
                GOOGLE_DRIVE_FILES_URL,
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=_DEFAULT_TIMEOUT,
            )
            data = resp.json()
        except Exception as exc:
            raise IntegrationProviderError(f"Drive list files failed: {exc}") from exc

        if resp.status_code != 200:
            raise IntegrationProviderError(
                f"Drive list files failed: {data}",
                status_code=resp.status_code,
                response_data=data if isinstance(data, dict) else {},
            )

        files = data.get("files", [])
        return [
            {
                "id": f.get("id"),
                "name": f.get("name"),
                "mimeType": f.get("mimeType"),
                "modifiedTime": f.get("modifiedTime"),
            }
            for f in files
        ]

    def get_file_metadata(self, access_token: str, file_id: str) -> dict[str, Any]:
        try:
            resp = requests.get(
                f"{GOOGLE_DRIVE_FILES_URL}/{file_id}",
                params={"fields": "id,name,mimeType,modifiedTime"},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=_DEFAULT_TIMEOUT,
            )
            data = resp.json()
        except Exception as exc:
            raise IntegrationProviderError(f"Drive get file failed: {exc}") from exc

        if resp.status_code != 200:
            raise IntegrationProviderError(
                f"Drive get file failed: {data}",
                status_code=resp.status_code,
                response_data=data if isinstance(data, dict) else {},
            )
        return data

    def download_file_content(
        self,
        access_token: str,
        file_id: str,
        *,
        mime_type: str | None = None,
        file_name: str | None = None,
    ) -> tuple[bytes, str, str]:
        """
        Download file bytes from Drive.

        Returns (content_bytes, file_name, mime_type).
        Google Workspace files are exported to text-friendly formats.
        """
        meta = self.get_file_metadata(access_token, file_id)
        mime_type = mime_type or meta.get("mimeType") or ""
        file_name = file_name or meta.get("name") or file_id

        if mime_type == "application/vnd.google-apps.folder":
            raise IntegrationProviderError("Cannot import a Drive folder.")

        if mime_type in GOOGLE_EXPORT_MIME:
            export_mime = GOOGLE_EXPORT_MIME[mime_type]
            url = f"{GOOGLE_DRIVE_FILES_URL}/{file_id}/export"
            params = {"mimeType": export_mime}
            effective_mime = export_mime
        else:
            if not any(mime_type.startswith(p) for p in _IMPORTABLE_MIME_PREFIXES):
                raise IntegrationProviderError(
                    f"Unsupported Drive file type: {mime_type or 'unknown'}"
                )
            url = f"{GOOGLE_DRIVE_FILES_URL}/{file_id}"
            params = {"alt": "media"}
            effective_mime = mime_type

        try:
            resp = requests.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=60,
            )
        except Exception as exc:
            raise IntegrationProviderError(f"Drive download failed: {exc}") from exc

        if resp.status_code != 200:
            try:
                err = resp.json()
            except Exception:
                err = resp.text
            raise IntegrationProviderError(
                f"Drive download failed: {err}",
                status_code=resp.status_code,
            )

        return resp.content, file_name, effective_mime

    def build_metadata_from_token_response(
        self,
        token_data: dict[str, Any],
        account_info: dict[str, Any],
    ) -> dict[str, Any]:
        meta = super().build_metadata_from_token_response(token_data, account_info)
        meta["account_email"] = account_info.get("email") or meta.get("account_email")
        return meta
