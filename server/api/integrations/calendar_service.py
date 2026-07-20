"""
Google Calendar API helpers for connected integrations.
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth.models import User

from api.integrations.models import IntegrationProvider
from api.integrations.providers import IntegrationProviderError, get_provider
from api.integrations.services import (
    ensure_valid_access_token,
    get_google_client_id,
    get_google_client_secret,
    get_integration_for_owner,
    parse_owner_type,
)


def _calendar_provider(access_token: str):
    return get_provider(
        IntegrationProvider.GOOGLE_CALENDAR,
        client_id=get_google_client_id(),
        client_secret=get_google_client_secret(),
        redirect_uri="",
        access_token=access_token,
    )


def get_calendar_integration_for_owner(
    *,
    user: User,
    owner_type: str,
    organization,
):
    owner = parse_owner_type(owner_type)
    return get_integration_for_owner(
        provider=IntegrationProvider.GOOGLE_CALENDAR,
        owner_type=owner,
        user=user,
        organization=organization,
    )


def _access_token_for_owner(*, user: User, owner_type: str, organization) -> str:
    integration = get_calendar_integration_for_owner(
        user=user,
        owner_type=owner_type,
        organization=organization,
    )
    if integration is None:
        raise IntegrationProviderError(
            "No Google Calendar integration connected for this owner."
        )
    return ensure_valid_access_token(integration)


def list_calendars_for_user(
    *,
    user: User,
    owner_type: str,
    organization,
) -> list[dict[str, Any]]:
    access_token = _access_token_for_owner(
        user=user, owner_type=owner_type, organization=organization
    )
    provider = _calendar_provider(access_token)
    return provider.list_calendars(access_token)


def list_events_for_user(
    *,
    user: User,
    owner_type: str,
    organization,
    calendar_id: str = "primary",
    time_min: str | None = None,
    time_max: str | None = None,
    max_results: int = 50,
) -> list[dict[str, Any]]:
    access_token = _access_token_for_owner(
        user=user, owner_type=owner_type, organization=organization
    )
    provider = _calendar_provider(access_token)
    return provider.list_events(
        access_token,
        calendar_id=calendar_id,
        time_min=time_min,
        time_max=time_max,
        max_results=max_results,
    )


def build_google_event_body(payload: dict[str, Any]) -> dict[str, Any]:
    """Map API payload to Google Calendar event resource."""
    body: dict[str, Any] = {}
    for key in ("summary", "description", "location", "start", "end"):
        if key in payload and payload[key] is not None:
            body[key] = payload[key]

    attendees = payload.get("attendees")
    if attendees is not None:
        if not isinstance(attendees, list):
            raise IntegrationProviderError("attendees must be a list of { email } objects.")
        body["attendees"] = [{"email": a.get("email")} for a in attendees if a.get("email")]

    if "start" not in body or "end" not in body:
        raise IntegrationProviderError("start and end are required for calendar events.")

    return body


def create_event_for_user(
    *,
    user: User,
    owner_type: str,
    organization,
    calendar_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    access_token = _access_token_for_owner(
        user=user, owner_type=owner_type, organization=organization
    )
    provider = _calendar_provider(access_token)
    event_body = build_google_event_body(payload)
    return provider.create_event(
        access_token,
        calendar_id=calendar_id,
        event_body=event_body,
    )


def update_event_for_user(
    *,
    user: User,
    owner_type: str,
    organization,
    calendar_id: str,
    event_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    access_token = _access_token_for_owner(
        user=user, owner_type=owner_type, organization=organization
    )
    provider = _calendar_provider(access_token)
    patch_body: dict[str, Any] = {}
    for key in ("summary", "description", "location", "start", "end"):
        if key in payload and payload[key] is not None:
            patch_body[key] = payload[key]
    if "attendees" in payload:
        attendees = payload.get("attendees")
        if attendees is not None:
            if not isinstance(attendees, list):
                raise IntegrationProviderError("attendees must be a list of { email } objects.")
            patch_body["attendees"] = [
                {"email": a.get("email")} for a in attendees if a.get("email")
            ]
    if not patch_body:
        raise IntegrationProviderError("No fields to update.")

    return provider.update_event(
        access_token,
        calendar_id=calendar_id,
        event_id=event_id,
        event_body=patch_body,
    )


def delete_event_for_user(
    *,
    user: User,
    owner_type: str,
    organization,
    calendar_id: str,
    event_id: str,
) -> None:
    access_token = _access_token_for_owner(
        user=user, owner_type=owner_type, organization=organization
    )
    provider = _calendar_provider(access_token)
    provider.delete_event(
        access_token,
        calendar_id=calendar_id,
        event_id=event_id,
    )
