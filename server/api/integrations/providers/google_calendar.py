"""
Google Calendar integration provider (OAuth + Calendar API v3).
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlencode

import requests

from .base import IntegrationProvider, IntegrationProviderError
from .google_oauth import (
    DEFAULT_TIMEOUT,
    GOOGLE_AUTH_URL,
    GOOGLE_TOKEN_URL,
    GOOGLE_USERINFO_URL,
    IDENTITY_SCOPES,
)

CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"
ALL_SCOPES = f"{IDENTITY_SCOPES} {CALENDAR_SCOPE}"
CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"

_EVENT_FIELDS = (
    "id,summary,description,location,htmlLink,status,start,end,attendees"
)


class GoogleCalendarProvider(IntegrationProvider):
    provider_key = "google_calendar"

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
            resp = requests.post(GOOGLE_TOKEN_URL, data=payload, timeout=DEFAULT_TIMEOUT)
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
                timeout=DEFAULT_TIMEOUT,
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

    def list_calendars(self, access_token: str) -> list[dict[str, Any]]:
        try:
            resp = requests.get(
                f"{CALENDAR_API_BASE}/users/me/calendarList",
                params={"fields": "items(id,summary,description,primary,accessRole)"},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=DEFAULT_TIMEOUT,
            )
            data = resp.json()
        except Exception as exc:
            raise IntegrationProviderError(f"Calendar list failed: {exc}") from exc

        if resp.status_code != 200:
            raise IntegrationProviderError(
                f"Calendar list failed: {data}",
                status_code=resp.status_code,
                response_data=data if isinstance(data, dict) else {},
            )

        return [
            {
                "id": item.get("id"),
                "summary": item.get("summary"),
                "description": item.get("description"),
                "primary": item.get("primary", False),
                "accessRole": item.get("accessRole"),
            }
            for item in data.get("items", [])
        ]

    def get_calendar_timezone(self, access_token: str, *, calendar_id: str = "primary") -> str:
        cal_path = quote(calendar_id, safe="")
        try:
            resp = requests.get(
                f"{CALENDAR_API_BASE}/calendars/{cal_path}",
                params={"fields": "timeZone"},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=DEFAULT_TIMEOUT,
            )
            data = resp.json()
        except Exception as exc:
            raise IntegrationProviderError(f"Calendar timezone lookup failed: {exc}") from exc

        if resp.status_code != 200:
            raise IntegrationProviderError(
                f"Calendar timezone lookup failed: {data}",
                status_code=resp.status_code,
                response_data=data if isinstance(data, dict) else {},
            )
        tz = (data.get("timeZone") or "").strip()
        if not tz:
            raise IntegrationProviderError("Calendar has no timeZone field.")
        return tz

    def list_events(
        self,
        access_token: str,
        *,
        calendar_id: str = "primary",
        time_min: str | None = None,
        time_max: str | None = None,
        max_results: int = 50,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "maxResults": min(max(max_results, 1), 250),
            "singleEvents": "true",
            "orderBy": "startTime",
            "fields": f"items({_EVENT_FIELDS})",
        }
        if time_min:
            params["timeMin"] = time_min
        if time_max:
            params["timeMax"] = time_max

        cal_path = quote(calendar_id, safe="")
        try:
            resp = requests.get(
                f"{CALENDAR_API_BASE}/calendars/{cal_path}/events",
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=DEFAULT_TIMEOUT,
            )
            data = resp.json()
        except Exception as exc:
            raise IntegrationProviderError(f"Calendar list events failed: {exc}") from exc

        if resp.status_code != 200:
            raise IntegrationProviderError(
                f"Calendar list events failed: {data}",
                status_code=resp.status_code,
                response_data=data if isinstance(data, dict) else {},
            )

        return [self._normalize_event(item) for item in data.get("items", [])]

    def create_event(
        self,
        access_token: str,
        *,
        calendar_id: str,
        event_body: dict[str, Any],
    ) -> dict[str, Any]:
        cal_path = quote(calendar_id, safe="")
        try:
            resp = requests.post(
                f"{CALENDAR_API_BASE}/calendars/{cal_path}/events",
                params={"fields": _EVENT_FIELDS},
                json=event_body,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=DEFAULT_TIMEOUT,
            )
            data = resp.json()
        except Exception as exc:
            raise IntegrationProviderError(f"Calendar create event failed: {exc}") from exc

        if resp.status_code not in (200, 201):
            raise IntegrationProviderError(
                f"Calendar create event failed: {data}",
                status_code=resp.status_code,
                response_data=data if isinstance(data, dict) else {},
            )
        return self._normalize_event(data)

    def get_event(
        self,
        access_token: str,
        *,
        calendar_id: str,
        event_id: str,
    ) -> dict[str, Any]:
        cal_path = quote(calendar_id, safe="")
        ev_path = quote(event_id, safe="")
        try:
            resp = requests.get(
                f"{CALENDAR_API_BASE}/calendars/{cal_path}/events/{ev_path}",
                params={"fields": _EVENT_FIELDS},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=DEFAULT_TIMEOUT,
            )
            data = resp.json()
        except Exception as exc:
            raise IntegrationProviderError(f"Calendar get event failed: {exc}") from exc

        if resp.status_code != 200:
            raise IntegrationProviderError(
                f"Calendar get event failed: {data}",
                status_code=resp.status_code,
                response_data=data if isinstance(data, dict) else {},
            )
        return self._normalize_event(data)

    def update_event(
        self,
        access_token: str,
        *,
        calendar_id: str,
        event_id: str,
        event_body: dict[str, Any],
    ) -> dict[str, Any]:
        cal_path = quote(calendar_id, safe="")
        ev_path = quote(event_id, safe="")
        try:
            resp = requests.patch(
                f"{CALENDAR_API_BASE}/calendars/{cal_path}/events/{ev_path}",
                params={"fields": _EVENT_FIELDS},
                json=event_body,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=DEFAULT_TIMEOUT,
            )
            data = resp.json()
        except Exception as exc:
            raise IntegrationProviderError(f"Calendar update event failed: {exc}") from exc

        if resp.status_code != 200:
            raise IntegrationProviderError(
                f"Calendar update event failed: {data}",
                status_code=resp.status_code,
                response_data=data if isinstance(data, dict) else {},
            )
        return self._normalize_event(data)

    def delete_event(
        self,
        access_token: str,
        *,
        calendar_id: str,
        event_id: str,
    ) -> None:
        cal_path = quote(calendar_id, safe="")
        ev_path = quote(event_id, safe="")
        try:
            resp = requests.delete(
                f"{CALENDAR_API_BASE}/calendars/{cal_path}/events/{ev_path}",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=DEFAULT_TIMEOUT,
            )
        except Exception as exc:
            raise IntegrationProviderError(f"Calendar delete event failed: {exc}") from exc

        if resp.status_code not in (200, 204):
            try:
                err = resp.json()
            except Exception:
                err = resp.text
            raise IntegrationProviderError(
                f"Calendar delete event failed: {err}",
                status_code=resp.status_code,
            )

    @staticmethod
    def _normalize_event(raw: dict[str, Any]) -> dict[str, Any]:
        attendees = raw.get("attendees") or []
        return {
            "id": raw.get("id"),
            "summary": raw.get("summary"),
            "description": raw.get("description"),
            "location": raw.get("location"),
            "htmlLink": raw.get("htmlLink"),
            "status": raw.get("status"),
            "start": raw.get("start"),
            "end": raw.get("end"),
            "attendees": [{"email": a.get("email")} for a in attendees if a.get("email")],
        }

    def build_metadata_from_token_response(
        self,
        token_data: dict[str, Any],
        account_info: dict[str, Any],
    ) -> dict[str, Any]:
        meta = super().build_metadata_from_token_response(token_data, account_info)
        meta["account_email"] = account_info.get("email") or meta.get("account_email")
        return meta
