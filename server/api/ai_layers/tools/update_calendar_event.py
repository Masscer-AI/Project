"""
Tool: update_calendar_event — update an event on the user's connected Google Calendar.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from api.ai_layers.tools.calendar_tool_helpers import (
    google_event_time,
    require_calendar_tool_context,
    resolve_guest_emails,
)
from api.integrations.calendar_service import update_event_for_user


class UpdateCalendarEventParams(BaseModel):
    event_id: str = Field(description="Google Calendar event id from list_calendar_events.")
    summary: str | None = None
    description: str | None = None
    location: str | None = None
    start: str | None = None
    end: str | None = None
    guest_user_ids: list[int] | None = Field(
        default=None,
        description="When set, replaces attendees with resolved org member emails.",
    )
    calendar_id: str = Field(default="primary")


class UpdateCalendarEventResult(BaseModel):
    event: dict
    skipped_no_email_count: int = 0
    timezone: str


def _update_calendar_event_impl(
    *,
    event_id: str,
    summary: str | None,
    description: str | None,
    location: str | None,
    start: str | None,
    end: str | None,
    guest_user_ids: list[int] | None,
    calendar_id: str,
    user_id: int,
    organization_id: int,
) -> UpdateCalendarEventResult:
    user, org, tz_name = require_calendar_tool_context(
        user_id=user_id,
        organization_id=organization_id,
    )
    payload: dict = {}
    if summary is not None:
        payload["summary"] = summary
    if description is not None:
        payload["description"] = description
    if location is not None:
        payload["location"] = location
    if start is not None:
        payload["start"] = google_event_time(start, tz_name)
    if end is not None:
        payload["end"] = google_event_time(end, tz_name)

    skipped = 0
    if guest_user_ids is not None:
        attendees, skipped = resolve_guest_emails(guest_user_ids, org)
        payload["attendees"] = attendees

    event = update_event_for_user(
        user=user,
        owner_type="user",
        organization=None,
        calendar_id=calendar_id,
        event_id=event_id,
        payload=payload,
    )
    return UpdateCalendarEventResult(
        event=event,
        skipped_no_email_count=skipped,
        timezone=tz_name,
    )


def get_tool(
    user_id: int | None = None,
    organization_id: int | None = None,
    **kwargs,
) -> dict:
    if user_id is None:
        raise ValueError("update_calendar_event requires user_id in tool context")
    if organization_id is None:
        raise ValueError("update_calendar_event requires organization_id in tool context")

    def update_calendar_event(
        event_id: str,
        summary: str | None = None,
        description: str | None = None,
        location: str | None = None,
        start: str | None = None,
        end: str | None = None,
        guest_user_ids: list[int] | None = None,
        calendar_id: str = "primary",
    ) -> UpdateCalendarEventResult:
        return _update_calendar_event_impl(
            event_id=event_id,
            summary=summary,
            description=description,
            location=location,
            start=start,
            end=end,
            guest_user_ids=guest_user_ids,
            calendar_id=calendar_id,
            user_id=user_id,
            organization_id=organization_id,
        )

    return {
        "name": "update_calendar_event",
        "description": (
            "Update an existing event on the user's connected Google Calendar. "
            "Requires event_id from list_calendar_events. "
            "Only include fields to change. guest_user_ids replaces all attendees when provided."
        ),
        "parameters": UpdateCalendarEventParams,
        "function": update_calendar_event,
    }
