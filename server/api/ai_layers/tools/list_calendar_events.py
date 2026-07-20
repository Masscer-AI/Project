"""
Tool: list_calendar_events — list events on the user's connected Google Calendar.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from api.ai_layers.tools.calendar_tool_helpers import (
    TimeframePreset,
    require_calendar_tool_context,
    window_for_timeframe,
)
from api.integrations.calendar_service import list_events_for_user


class ListCalendarEventsParams(BaseModel):
    timeframe: TimeframePreset = Field(
        default="today",
        description=(
            "Time window: today, tomorrow, this_week, next_week, last_week, day, or custom. "
            "Use day with date; use custom with time_min and time_max (RFC3339 or local)."
        ),
    )
    date: str | None = Field(
        default=None,
        description="Required when timeframe=day (YYYY-MM-DD).",
    )
    time_min: str | None = Field(
        default=None,
        description="Required when timeframe=custom (start of range).",
    )
    time_max: str | None = Field(
        default=None,
        description="Required when timeframe=custom (end of range).",
    )
    max_results: int = Field(default=50, ge=1, le=100)
    calendar_id: str = Field(
        default="primary",
        description="Google calendar id within the connected account (default primary).",
    )


class CalendarEventSummary(BaseModel):
    id: str | None = None
    summary: str | None = None
    description: str | None = None
    location: str | None = None
    htmlLink: str | None = None
    status: str | None = None
    start: dict | None = None
    end: dict | None = None
    attendees: list[dict] | None = None


class ListCalendarEventsResult(BaseModel):
    events: list[CalendarEventSummary]
    calendar_id: str
    time_min: str
    time_max: str
    timezone: str


def _list_calendar_events_impl(
    *,
    timeframe: TimeframePreset,
    date: str | None,
    time_min: str | None,
    time_max: str | None,
    max_results: int,
    calendar_id: str,
    user_id: int,
    organization_id: int,
) -> ListCalendarEventsResult:
    user, _org, tz_name = require_calendar_tool_context(
        user_id=user_id,
        organization_id=organization_id,
    )
    t_min, t_max = window_for_timeframe(
        timeframe=timeframe,
        tz_name=tz_name,
        date_str=date,
        time_min=time_min,
        time_max=time_max,
    )
    events = list_events_for_user(
        user=user,
        owner_type="user",
        organization=None,
        calendar_id=calendar_id,
        time_min=t_min,
        time_max=t_max,
        max_results=max_results,
    )
    return ListCalendarEventsResult(
        events=[CalendarEventSummary.model_validate(e) for e in events],
        calendar_id=calendar_id,
        time_min=t_min,
        time_max=t_max,
        timezone=tz_name,
    )


def get_tool(
    user_id: int | None = None,
    organization_id: int | None = None,
    **kwargs,
) -> dict:
    if user_id is None:
        raise ValueError("list_calendar_events requires user_id in tool context")
    if organization_id is None:
        raise ValueError("list_calendar_events requires organization_id in tool context")

    def list_calendar_events(
        timeframe: TimeframePreset = "today",
        date: str | None = None,
        time_min: str | None = None,
        time_max: str | None = None,
        max_results: int = 50,
        calendar_id: str = "primary",
    ) -> ListCalendarEventsResult:
        return _list_calendar_events_impl(
            timeframe=timeframe,
            date=date,
            time_min=time_min,
            time_max=time_max,
            max_results=max_results,
            calendar_id=calendar_id,
            user_id=user_id,
            organization_id=organization_id,
        )

    return {
        "name": "list_calendar_events",
        "description": (
            "List events on the user's connected Google Calendar for a time window. "
            "Use timeframe presets (today, tomorrow, this_week, next_week, last_week) "
            "or timeframe=day with date, or timeframe=custom with time_min/time_max. "
            "Times are interpreted in the organization timezone unless offsets are provided. "
            "Default calendar_id is primary."
        ),
        "parameters": ListCalendarEventsParams,
        "function": list_calendar_events,
    }
