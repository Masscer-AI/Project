"""
Shared helpers for Google Calendar agent tools (timezones, presets, guests).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User

from api.authenticate.models import Organization
from api.authenticate.org_membership import user_belongs_to_organization

CALENDAR_AGENT_TOOL_NAMES: tuple[str, ...] = (
    "list_calendar_events",
    "create_calendar_event",
    "update_calendar_event",
)


def require_calendar_tool_context(
    *,
    user_id: int | None,
    organization_id: int | None,
) -> tuple[User, Organization, str]:
    if user_id is None:
        raise ValueError("Calendar tools require an authenticated user.")
    if organization_id is None:
        raise ValueError("Calendar tools require an organization context.")

    from api.integrations.services import user_has_personal_google_calendar

    if not user_has_personal_google_calendar(user_id):
        raise ValueError(
            "Google Calendar is not connected. Connect your personal calendar in Integrations first."
        )

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        raise ValueError("Authenticated user not found.")

    try:
        org = Organization.objects.get(pk=organization_id)
    except Organization.DoesNotExist:
        raise ValueError("Organization not found.")

    tz_name = resolve_org_timezone(organization_id)
    return user, org, tz_name


TimeframePreset = Literal[
    "today",
    "tomorrow",
    "this_week",
    "next_week",
    "last_week",
    "day",
    "custom",
]

_OFFSET_RE = re.compile(r"([zZ]|[+-]\d{2}:\d{2})$")


def resolve_org_timezone(organization_id: int | None) -> str:
    if not organization_id:
        return "UTC"
    try:
        org = Organization.objects.get(pk=organization_id)
    except Organization.DoesNotExist:
        return "UTC"
    tz = (org.timezone or "").strip()
    return tz or "UTC"


def window_for_timeframe(
    *,
    timeframe: TimeframePreset,
    tz_name: str,
    date_str: str | None = None,
    time_min: str | None = None,
    time_max: str | None = None,
    now: datetime | None = None,
) -> tuple[str, str]:
    """Return (time_min, time_max) as RFC3339 for Google Calendar API."""
    tz = ZoneInfo(tz_name)
    now_local = (now or datetime.now(tz)).astimezone(tz)

    def day_start(d: date) -> datetime:
        return datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=tz)

    def to_rfc(dt: datetime) -> str:
        return dt.isoformat()

    if timeframe == "custom":
        if not time_min or not time_max:
            raise ValueError("timeframe=custom requires time_min and time_max.")
        return _ensure_rfc3339(time_min, tz_name), _ensure_rfc3339(time_max, tz_name)

    if timeframe == "today":
        start = day_start(now_local.date())
        end = start + timedelta(days=1)
        return to_rfc(start), to_rfc(end)

    if timeframe == "tomorrow":
        start = day_start(now_local.date() + timedelta(days=1))
        end = start + timedelta(days=1)
        return to_rfc(start), to_rfc(end)

    if timeframe == "day":
        if not date_str:
            raise ValueError("timeframe=day requires date (YYYY-MM-DD).")
        d = date.fromisoformat(date_str)
        start = day_start(d)
        end = start + timedelta(days=1)
        return to_rfc(start), to_rfc(end)

    # Week boundaries: Monday 00:00 local
    this_monday = day_start(now_local.date() - timedelta(days=now_local.weekday()))

    if timeframe == "this_week":
        return to_rfc(this_monday), to_rfc(this_monday + timedelta(days=7))

    if timeframe == "next_week":
        start = this_monday + timedelta(days=7)
        return to_rfc(start), to_rfc(start + timedelta(days=7))

    if timeframe == "last_week":
        start = this_monday - timedelta(days=7)
        return to_rfc(start), to_rfc(this_monday)

    raise ValueError(f"Unknown timeframe: {timeframe}")


def _ensure_rfc3339(value: str, tz_name: str) -> str:
    raw = value.strip()
    if _OFFSET_RE.search(raw):
        return raw
    tz = ZoneInfo(tz_name)
    if "T" in raw:
        naive = datetime.fromisoformat(raw)
    else:
        naive = datetime.fromisoformat(f"{raw}T00:00:00")
    if naive.tzinfo is None:
        return naive.replace(tzinfo=tz).isoformat()
    return naive.isoformat()


def google_event_time(value: str, tz_name: str) -> dict[str, str]:
    """
    Build Google Calendar start/end object.

    Naive local times use timeZone; values with offset are passed as dateTime only.
    """
    raw = value.strip()
    if _OFFSET_RE.search(raw):
        return {"dateTime": raw}
    if "T" not in raw:
        return {"date": raw}
    return {"dateTime": raw, "timeZone": tz_name}


def resolve_guest_emails(
    guest_user_ids: list[int] | None,
    organization: Organization,
) -> tuple[list[dict[str, str]], int]:
    """Resolve org member user IDs to attendee emails. Returns (attendees, skipped_no_email)."""
    if not guest_user_ids:
        return [], 0

    users_by_id: dict[int, User] = {}
    for raw_id in guest_user_ids:
        user_id = int(raw_id)
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            raise ValueError(f"Guest user_id {user_id} not found.")
        if not user_belongs_to_organization(user, organization):
            raise ValueError(f"User {user_id} is not a member of this organization.")
        users_by_id[user.id] = user

    attendees: list[dict[str, str]] = []
    skipped = 0
    for user in users_by_id.values():
        email = (user.email or "").strip()
        if email:
            attendees.append({"email": email})
        else:
            skipped += 1
    return attendees, skipped


def format_org_timezone_clock_line(organization_id: int | None) -> str:
    tz_name = resolve_org_timezone(organization_id)
    return (
        f"Organization timezone for calendar scheduling: {tz_name}. "
        "Use this timezone for calendar tool start/end times unless the user specifies otherwise."
    )
