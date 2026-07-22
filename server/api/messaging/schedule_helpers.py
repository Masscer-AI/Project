"""
Helpers for ScheduledConversationTask: org-TZ parsing, cron building, next-run computation.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from croniter import croniter

ScheduleType = Literal["once", "recurring"]
Recurrence = Literal["daily", "weekly", "monthly"]

_OFFSET_RE = re.compile(r"([zZ]|[+-]\d{2}:\d{2})$")
_TIME_OF_DAY_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_CRON_FIELD_RE = re.compile(r"^[\d*/,\-]+$")

WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

# Our weekdays: 0=Mon … 6=Sun. Standard cron (croniter): 0=Sun, 1=Mon … 6=Sat.
def mon0_to_cron_dow(weekday: int) -> int:
    return (int(weekday) + 1) % 7


def parse_time_of_day(value: str) -> tuple[int, int]:
    raw = (value or "").strip()
    match = _TIME_OF_DAY_RE.match(raw)
    if not match:
        raise ValueError("time_of_day must be HH:MM in 24-hour format (e.g. 11:00).")
    return int(match.group(1)), int(match.group(2))


def parse_run_at_to_utc(value: str, tz_name: str) -> datetime:
    """
    Parse a run_at string to an aware UTC datetime.

    Naive datetimes (no Z/offset) are interpreted in the organization timezone.
    Values with an offset are converted to UTC.
    """
    raw = (value or "").strip()
    if not raw:
        raise ValueError("run_at is required.")

    tz = ZoneInfo(tz_name)
    if _OFFSET_RE.search(raw):
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00").replace("z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError("run_at with offset marker must be timezone-aware.")
        return dt.astimezone(ZoneInfo("UTC"))

    if "T" in raw:
        naive = datetime.fromisoformat(raw)
    else:
        naive = datetime.fromisoformat(f"{raw}T00:00:00")
    if naive.tzinfo is not None:
        return naive.astimezone(ZoneInfo("UTC"))
    return naive.replace(tzinfo=tz).astimezone(ZoneInfo("UTC"))


def validate_cron_expression(cron: str) -> str:
    parts = (cron or "").strip().split()
    if len(parts) != 5:
        raise ValueError("cron must be a 5-field expression: minute hour day month weekday.")
    for part in parts:
        if not _CRON_FIELD_RE.match(part):
            raise ValueError(f"Invalid cron field: {part!r}.")
    # Validate with croniter against a fixed base.
    base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
    try:
        croniter(" ".join(parts), base)
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"Invalid cron expression: {exc}") from exc
    return " ".join(parts)


def build_cron_from_structured(
    *,
    recurrence: Recurrence,
    time_of_day: str,
    weekdays: list[int] | None = None,
    day_of_month: int | None = None,
) -> str:
    hour, minute = parse_time_of_day(time_of_day)

    if recurrence == "daily":
        return f"{minute} {hour} * * *"

    if recurrence == "weekly":
        if not weekdays:
            raise ValueError("weekly recurrence requires weekdays (0=Mon … 6=Sun).")
        cleaned: list[int] = []
        for raw in weekdays:
            wd = int(raw)
            if wd < 0 or wd > 6:
                raise ValueError("weekdays must be integers 0=Mon … 6=Sun.")
            cleaned.append(wd)
        cleaned = sorted(set(cleaned))
        cron_dows = ",".join(str(mon0_to_cron_dow(wd)) for wd in cleaned)
        return f"{minute} {hour} * * {cron_dows}"

    if recurrence == "monthly":
        if day_of_month is None:
            raise ValueError("monthly recurrence requires day_of_month (1-31).")
        day = int(day_of_month)
        if day < 1 or day > 31:
            raise ValueError("day_of_month must be between 1 and 31.")
        return f"{minute} {hour} {day} * *"

    raise ValueError(f"Unsupported recurrence: {recurrence}")


def resolve_cron_expression(
    *,
    schedule_type: ScheduleType,
    recurrence: Recurrence | None = None,
    time_of_day: str | None = None,
    weekdays: list[int] | None = None,
    day_of_month: int | None = None,
    cron: str | None = None,
) -> str | None:
    """Return cron for recurring schedules, or None for once."""
    if schedule_type == "once":
        return None

    cron_raw = (cron or "").strip()
    if cron_raw:
        return validate_cron_expression(cron_raw)

    if not recurrence:
        raise ValueError("recurring schedules require recurrence or cron.")
    if not time_of_day:
        raise ValueError("recurring schedules require time_of_day when cron is omitted.")
    return build_cron_from_structured(
        recurrence=recurrence,
        time_of_day=time_of_day,
        weekdays=weekdays,
        day_of_month=day_of_month,
    )


def compute_next_run_at(
    *,
    schedule_type: ScheduleType,
    tz_name: str,
    run_at_utc: datetime | None = None,
    cron: str | None = None,
    after: datetime | None = None,
) -> datetime:
    """
    Compute the next UTC run instant.

    For once: returns run_at_utc (must be in the future relative to after).
    For recurring: next cron tick strictly after `after` in org TZ, returned as UTC.
    """
    now_utc = after or datetime.now(ZoneInfo("UTC"))
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=ZoneInfo("UTC"))
    else:
        now_utc = now_utc.astimezone(ZoneInfo("UTC"))

    if schedule_type == "once":
        if run_at_utc is None:
            raise ValueError("once schedules require run_at.")
        if run_at_utc.tzinfo is None:
            raise ValueError("run_at must be timezone-aware UTC.")
        run_utc = run_at_utc.astimezone(ZoneInfo("UTC"))
        if run_utc <= now_utc:
            raise ValueError("run_at must be in the future.")
        return run_utc

    if not cron:
        raise ValueError("recurring schedules require a cron expression.")

    tz = ZoneInfo(tz_name)
    # croniter's next() is exclusive of the base; use local "now" so wall clock matches org TZ.
    base_local = now_utc.astimezone(tz)
    iterator = croniter(cron, base_local)
    next_local = iterator.get_next(datetime)
    if next_local.tzinfo is None:
        next_local = next_local.replace(tzinfo=tz)
    else:
        next_local = next_local.astimezone(tz)
    return next_local.astimezone(ZoneInfo("UTC"))


def format_schedule_summary(
    *,
    schedule_type: ScheduleType,
    tz_name: str,
    next_run_at_utc: datetime,
    recurrence: Recurrence | None = None,
    time_of_day: str | None = None,
    weekdays: list[int] | None = None,
    day_of_month: int | None = None,
    cron: str | None = None,
) -> str:
    tz = ZoneInfo(tz_name)
    next_local = next_run_at_utc.astimezone(tz)
    next_local_str = next_local.strftime("%Y-%m-%d %H:%M")

    if schedule_type == "once":
        return f"Once at {next_local_str} ({tz_name})"

    if cron and not recurrence:
        return f"Cron `{cron}` in {tz_name}; next {next_local_str}"

    tod = time_of_day or next_local.strftime("%H:%M")
    if recurrence == "daily":
        return f"Every day at {tod} ({tz_name}); next {next_local_str}"
    if recurrence == "weekly":
        names = [
            WEEKDAY_NAMES[int(wd)]
            for wd in sorted(set(int(x) for x in (weekdays or [])))
            if 0 <= int(wd) <= 6
        ]
        day_label = ", ".join(names) if names else "selected days"
        return f"Every {day_label} at {tod} ({tz_name}); next {next_local_str}"
    if recurrence == "monthly":
        dom = day_of_month if day_of_month is not None else next_local.day
        return f"Monthly on day {dom} at {tod} ({tz_name}); next {next_local_str}"

    return f"Recurring in {tz_name}; next {next_local_str}"


def local_iso_from_utc(dt_utc: datetime, tz_name: str) -> str:
    tz = ZoneInfo(tz_name)
    local = dt_utc.astimezone(tz)
    return local.replace(tzinfo=None).isoformat(timespec="seconds")


def schedule_payload_dict(task: Any) -> dict[str, Any]:
    """Serialize a ScheduledConversationTask-like object for tool results."""
    next_run = task.next_run_at
    if next_run is not None and next_run.tzinfo is None:
        from django.utils import timezone as dj_tz

        next_run = dj_tz.make_aware(next_run, ZoneInfo("UTC"))

    summary = format_schedule_summary(
        schedule_type=task.schedule_type,
        tz_name=task.timezone,
        next_run_at_utc=next_run,
        recurrence=task.recurrence,
        time_of_day=task.time_of_day,
        weekdays=task.weekdays or [],
        day_of_month=task.day_of_month,
        cron=task.cron,
    )
    conversation = getattr(task, "conversation", None)
    conversation_id = str(task.conversation_id) if getattr(task, "conversation_id", None) else None
    conversation_title = None
    if conversation is not None:
        conversation_title = (getattr(conversation, "title", None) or "").strip() or None

    return {
        "id": str(task.id),
        "status": task.status,
        "schedule_type": task.schedule_type,
        "timezone": task.timezone,
        "next_run_at_utc": next_run.isoformat() if next_run else None,
        "next_run_at_local": local_iso_from_utc(next_run, task.timezone) if next_run else None,
        "schedule_summary": summary,
        "instruction": task.instruction_text,
        "recurrence": task.recurrence,
        "time_of_day": task.time_of_day,
        "weekdays": task.weekdays or [],
        "day_of_month": task.day_of_month,
        "cron": task.cron,
        "conversation_id": conversation_id,
        "conversation_title": conversation_title,
    }


# Small epsilon used when advancing recurring schedules after a run.
RECURRING_ADVANCE_EPSILON = timedelta(seconds=1)
