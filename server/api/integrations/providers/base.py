"""
Abstract base for third-party integration providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IntegrationProviderError(Exception):
    """Raised when a provider API returns an unexpected response."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_data: dict | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data or {}


class IntegrationProvider(ABC):
    """Provider-specific OAuth and API operations."""

    provider_key: str

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        access_token: str | None = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_token = access_token

    @abstractmethod
    def get_authorization_url(self, state: str) -> str:
        """Build the OAuth authorization URL."""

    @abstractmethod
    def exchange_code_for_token(self, code: str) -> dict[str, Any]:
        """Exchange authorization code for tokens."""

    @abstractmethod
    def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        """Refresh an expired access token."""

    @abstractmethod
    def fetch_account_info(self, access_token: str) -> dict[str, Any]:
        """Fetch account metadata after connect (email, label, etc.)."""

    def list_files(self, access_token: str, *, limit: int = 20) -> list[dict[str, Any]]:
        """List files in the linked account (Drive-only; optional for other providers)."""
        raise NotImplementedError(f"{self.provider_key} does not support list_files")

    def build_metadata_from_token_response(
        self,
        token_data: dict[str, Any],
        account_info: dict[str, Any],
    ) -> dict[str, Any]:
        """Default metadata builder; providers may override."""
        scope_raw = token_data.get("scope", "")
        scopes = scope_raw.split() if isinstance(scope_raw, str) else list(scope_raw or [])
        return {
            "account_email": account_info.get("email"),
            "granted_scopes": scopes,
        }
