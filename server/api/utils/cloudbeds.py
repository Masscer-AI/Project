"""
CloudBedsIntegration — service layer for the Cloudbeds PMS API.

Handles:
  - OAuth 2.0 authorization URL generation
  - Authorization-code → token exchange
  - Access-token refresh
  - Authenticated HTTP calls to the Cloudbeds REST API

Usage:
    from api.utils.cloudbeds import CloudBedsIntegration

    # Build the redirect URL to send the user to Cloudbeds
    url = CloudBedsIntegration.get_authorization_url(
        client_id="...",
        redirect_uri="https://yourapp.com/v1/cloudbeds/callback/",
        state="random-csrf-token",
    )

    # After the user grants access, exchange the code for a token
    integration = CloudBedsIntegration()
    token_data = integration.exchange_code_for_token(
        client_id="...",
        client_secret="...",
        redirect_uri="https://yourapp.com/v1/cloudbeds/callback/",
        code=request.GET["code"],
    )
    access_token = token_data["access_token"]

    # Make authenticated API calls
    cb = CloudBedsIntegration(access_token=access_token)
    property_info = cb.get_property_info()
    dashboard     = cb.get_dashboard()
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cloudbeds API constants
# ---------------------------------------------------------------------------

CLOUDBEDS_API_BASE = "https://hotels.cloudbeds.com/api/v1.2"
CLOUDBEDS_OAUTH_URL = "https://hotels.cloudbeds.com/api/v1.2/oauth"
CLOUDBEDS_TOKEN_URL = "https://hotels.cloudbeds.com/api/v1.2/access_token"

# Default scopes requested during OAuth.
# These map directly to Cloudbeds API endpoint groups — only request what the
# app actually needs. Invalid scope names cause an invalid_scope OAuth error.
DEFAULT_SCOPES = [
    "read:reservation",
    "write:reservation",
    "read:guest",
    "write:guest",
    "read:room",
    "write:room",
    "read:rate",
    "write:rate",
]

_DEFAULT_TIMEOUT = 20  # seconds


class CloudBedsError(Exception):
    """Raised when the Cloudbeds API returns an unexpected response."""

    def __init__(self, message: str, status_code: int | None = None, response_data: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data or {}


class CloudBedsIntegration:
    """
    Thin wrapper around the Cloudbeds REST API.

    Stateless static helpers handle the OAuth flow (no access token required).
    Instance methods require a valid access_token.
    """

    def __init__(self, access_token: str | None = None):
        self.access_token = access_token

    # ------------------------------------------------------------------
    # OAuth helpers (static — no token needed)
    # ------------------------------------------------------------------

    @staticmethod
    def get_authorization_url(
        client_id: str,
        redirect_uri: str,
        state: str = "",
        scopes: list[str] | None = None,
    ) -> str:
        """
        Build the Cloudbeds OAuth 2.0 authorization URL.

        Redirect your user to this URL. After granting access, Cloudbeds
        will redirect them back to `redirect_uri?code=...&state=...`.

        Args:
            client_id:    Your Cloudbeds application client ID.
            redirect_uri: The callback URL registered in your app settings.
            state:        CSRF token (stored in session, verified on callback).
            scopes:       List of permission scopes; defaults to DEFAULT_SCOPES.

        Returns:
            Fully-formed authorization URL string.
        """
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes or DEFAULT_SCOPES),
        }
        if state:
            params["state"] = state

        return f"{CLOUDBEDS_OAUTH_URL}?{urlencode(params)}"

    @staticmethod
    def exchange_code_for_token(
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        code: str,
    ) -> dict:
        """
        Exchange an authorization code for an access + refresh token.

        Returns a dict with keys:
            access_token, refresh_token, token_type, expires_in, (property_id).

        Raises:
            CloudBedsError on HTTP errors or missing token in response.
        """
        payload = {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "code": code,
        }
        try:
            resp = requests.post(CLOUDBEDS_TOKEN_URL, data=payload, timeout=_DEFAULT_TIMEOUT)
            data = resp.json()
        except Exception as exc:
            raise CloudBedsError(f"Token exchange request failed: {exc}") from exc

        if resp.status_code != 200 or "access_token" not in data:
            raise CloudBedsError(
                f"Token exchange failed: {data.get('error_description', data)}",
                status_code=resp.status_code,
                response_data=data,
            )

        logger.info("Cloudbeds token exchange successful (property_id=%s)", data.get("property_id"))
        return data

    @staticmethod
    def refresh_access_token(
        client_id: str,
        client_secret: str,
        refresh_token: str,
    ) -> dict:
        """
        Use a refresh token to obtain a new access token.

        Returns updated token dict (same shape as exchange_code_for_token).

        Raises:
            CloudBedsError on failure.
        """
        payload = {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        }
        try:
            resp = requests.post(CLOUDBEDS_TOKEN_URL, data=payload, timeout=_DEFAULT_TIMEOUT)
            data = resp.json()
        except Exception as exc:
            raise CloudBedsError(f"Token refresh request failed: {exc}") from exc

        if resp.status_code != 200 or "access_token" not in data:
            raise CloudBedsError(
                f"Token refresh failed: {data.get('error_description', data)}",
                status_code=resp.status_code,
                response_data=data,
            )

        logger.info("Cloudbeds token refreshed successfully")
        return data

    # ------------------------------------------------------------------
    # Internal request helper
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json_body: dict | None = None,
    ) -> Any:
        """
        Make an authenticated request to the Cloudbeds API.

        Args:
            method:   HTTP method ("GET", "POST", etc.)
            endpoint: Path relative to CLOUDBEDS_API_BASE, e.g. "/getDashboard"
            params:   Query parameters dict.
            json_body: JSON body for POST requests.

        Returns:
            Parsed JSON response (usually a dict).

        Raises:
            CloudBedsError if the request fails or the API returns an error.
            ValueError  if this instance has no access_token.
        """
        if not self.access_token:
            raise ValueError("CloudBedsIntegration requires an access_token for API calls.")

        url = f"{CLOUDBEDS_API_BASE}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

        try:
            resp = requests.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json_body,
                timeout=_DEFAULT_TIMEOUT,
            )
            data = resp.json()
        except Exception as exc:
            raise CloudBedsError(f"Cloudbeds API request failed: {exc}") from exc

        if not resp.ok:
            raise CloudBedsError(
                f"Cloudbeds API error {resp.status_code}: {data.get('message', data)}",
                status_code=resp.status_code,
                response_data=data,
            )

        # Cloudbeds wraps responses in {"success": true, "data": {...}}
        if isinstance(data, dict) and data.get("success") is False:
            raise CloudBedsError(
                f"Cloudbeds returned success=false: {data.get('message', data)}",
                status_code=resp.status_code,
                response_data=data,
            )

        return data

    # ------------------------------------------------------------------
    # API methods
    # ------------------------------------------------------------------

    def get_property_info(self) -> dict:
        """
        Return information about the property linked to the current access token.

        Calls GET /userinfo.
        """
        return self._request("GET", "/userinfo")

    def get_dashboard(self) -> dict:
        """
        Return basic hotel dashboard information (occupancy, arrivals, etc.).

        Calls GET /getDashboard.
        """
        return self._request("GET", "/getDashboard")

    def list_reservations(
        self,
        status: str | None = None,
        page_number: int = 1,
        page_size: int = 25,
        extra_params: dict | None = None,
    ) -> dict:
        """
        Return a paginated list of reservations.

        Calls GET /getReservations.

        Args:
            status:       Optional status filter (e.g. "confirmed", "checked_in").
            page_number:  1-based page index.
            page_size:    Results per page (max 100).
            extra_params: Any additional query parameters.
        """
        params: dict = {
            "pageNumber": page_number,
            "pageSize": page_size,
        }
        if status:
            params["status"] = status
        if extra_params:
            params.update(extra_params)
        return self._request("GET", "/getReservations", params=params)

    def get_reservation(self, reservation_id: str) -> dict:
        """Return a single reservation by ID. Calls GET /getReservation."""
        return self._request("GET", "/getReservation", params={"reservationID": reservation_id})

    def list_rooms(self) -> dict:
        """Return the list of rooms / accommodation types. Calls GET /getRooms."""
        return self._request("GET", "/getRooms")

    # ------------------------------------------------------------------
    # Convenience: build an integration from a stored credential
    # ------------------------------------------------------------------

    @classmethod
    def from_credential(cls, credential: "CloudbedsCredential") -> "CloudBedsIntegration":  # noqa: F821
        """
        Instantiate from a stored CloudbedsCredential model object.

        Automatically refreshes the token if it is expired.

        Args:
            credential: A CloudbedsCredential Django model instance.

        Returns:
            CloudBedsIntegration ready to make API calls.
        """
        import os
        from django.utils import timezone

        client_id = os.environ.get("CLOUDBEDS_CLIENT_ID", "")
        client_secret = os.environ.get("CLOUDBEDS_CLIENT_SECRET", "")

        # Refresh if expired (with a 60-second buffer)
        if (
            credential.expires_at
            and credential.refresh_token
            and client_id
            and client_secret
        ):
            buffer = timezone.timedelta(seconds=60)
            if credential.expires_at - buffer <= timezone.now():
                try:
                    token_data = cls.refresh_access_token(
                        client_id=client_id,
                        client_secret=client_secret,
                        refresh_token=credential.refresh_token,
                    )
                    credential.access_token = token_data["access_token"]
                    if "refresh_token" in token_data:
                        credential.refresh_token = token_data["refresh_token"]
                    if "expires_in" in token_data:
                        credential.expires_at = timezone.now() + timezone.timedelta(
                            seconds=int(token_data["expires_in"])
                        )
                    credential.save(update_fields=["access_token", "refresh_token", "expires_at", "updated_at"])
                    logger.info("Cloudbeds token auto-refreshed for credential id=%s", credential.pk)
                except CloudBedsError as exc:
                    logger.error("Failed to auto-refresh Cloudbeds token: %s", exc)

        return cls(access_token=credential.access_token)
