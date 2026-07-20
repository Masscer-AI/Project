"""
Tool: create_calendar_event — create an event on the user's connected Google Calendar.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from api.ai_layers.tools.calendar_tool_helpers import (
    google_event_time,
    require_calendar_tool_context,
    resolve_guest_emails,
)
from api.integrations.calendar_service import create_event_for_user


class CreateCalendarEventParams(BaseModel):
    summary: str = Field(description="Event title.")
    start: str = Field(
        description=(
            "Start time: YYYY-MM-DDTHH:MM:SS in organization timezone, or RFC3339 with offset."
        ),
    )
    end: str = Field(description="End time (same format as start).")
    description: str | None = None
    location: str | None = None
    guest_user_ids: list[int] = Field(
        default_factory=list,
        description=(
            "Org member user IDs to invite. Use list_organization_members to find IDs. "
            "Emails are resolved server-side."
        ),
    )
    calendar_id: str = Field(default="primary")


class CreateCalendarEventResult(BaseModel):
    event: dict
    skipped_no_email_count: int = 0
    timezone: str


def _create_calendar_event_impl(
    *,
    summary: str,
    start: str,
    end: str,
    description: str | None,
    location: str | None,
    guest_user_ids: list[int],
    calendar_id: str,
    user_id: int,
    organization_id: int,
) -> CreateCalendarEventResult:
    user, org, tz_name = require_calendar_tool_context(
        user_id=user_id,
        organization_id=organization_id,
    )
    attendees, skipped = resolve_guest_emails(guest_user_ids, org)
    payload: dict = {
        "summary": summary,
        "start": google_event_time(start, tz_name),
        "end": google_event_time(end, tz_name),
    }
    if description:
        payload["description"] = description
    if location:
        payload["location"] = location
    if attendees:
        payload["attendees"] = attendees

    event = create_event_for_user(
        user=user,
        owner_type="user",
        organization=None,
        calendar_id=calendar_id,
        payload=payload,
    )
    return CreateCalendarEventResult(
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
        raise ValueError("create_calendar_event requires user_id in tool context")
    if organization_id is None:
        raise ValueError("create_calendar_event requires organization_id in tool context")

    def create_calendar_event(
        summary: str,
        start: str,
        end: str,
        description: str | None = None,
        location: str | None = None,
        guest_user_ids: list[int] | None = None,
        calendar_id: str = "primary",
    ) -> CreateCalendarEventResult:
        return _create_calendar_event_impl(
            summary=summary,
            start=start,
            end=end,
            description=description,
            location=location,
            guest_user_ids=guest_user_ids or [],
            calendar_id=calendar_id,
            user_id=user_id,
            organization_id=organization_id,
        )

    return {
        "name": "create_calendar_event",
        "description": (
            "Create an event on the user's connected Google Calendar. "
            "Pass start/end as local wall times (YYYY-MM-DDTHH:MM:SS) in the organization timezone "
            "unless you include a UTC offset. "
            "Invite org members with guest_user_ids (not raw emails). "
            "Use list_calendar_events to verify conflicts when helpful."
        ),
        "parameters": CreateCalendarEventParams,
        "function": create_calendar_event,
    }
