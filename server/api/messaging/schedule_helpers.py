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

# Legacy fallback when a scheduled task has an empty capabilities snapshot.
SCHEDULER_BASELINE_TOOL_NAMES: list[str] = [
    "read_attachment",
    "list_attachments",
    "update_attachment_visibility",
    "generate_document_file",
    "generate_excel_file",
    "send_email",
    "list_organization_members",
    "list_organization_roles",
    "explore_web",
    "rag_query",
    "list_knowledge_base_documents",
    "read_knowledge_base_document",
]

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
        "title": (getattr(task, "title", None) or "").strip() or None,
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
        "capabilities": list(getattr(task, "capabilities", None) or []),
        "agent_slugs": list(getattr(task, "agent_slugs", None) or []),
        "multiagentic_modality": getattr(task, "multiagentic_modality", None) or "isolated",
        "conversation_id": conversation_id,
        "conversation_title": conversation_title,
    }


def normalize_capability_names(raw: list | None) -> list[str]:
    """Deduplicate and keep only names registered in TOOL_REGISTRY (order preserved)."""
    from api.ai_layers.tools import TOOL_REGISTRY, canonical_tool_name

    seen: set[str] = set()
    out: list[str] = []
    for item in raw or []:
        if not isinstance(item, str):
            continue
        name = canonical_tool_name(item.strip())
        if not name or name not in TOOL_REGISTRY or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def selectable_scheduled_task_tool_names() -> list[str]:
    """
    Legacy helper: tools that used to be assignable on a scheduled-task allowlist.

    Schedule-management tools are excluded. Prefer Agent.pre_approved_tools for
    execution; this remains for older callers/tests.
    """
    from api.ai_layers.tools import SCHEDULE_AGENT_TOOL_NAMES, TOOL_REGISTRY

    blocked = frozenset(SCHEDULE_AGENT_TOOL_NAMES)
    return [name for name in TOOL_REGISTRY if name not in blocked]


def resolve_scheduled_task_capabilities(task) -> list[str] | None:
    """
    Legacy: explicit capability allowlist, or None for unconstrained.

    Scheduled execution no longer reads this field; kept for older payloads/tests.
    """
    from api.ai_layers.tools import SCHEDULE_AGENT_TOOL_NAMES

    caps = normalize_capability_names(getattr(task, "capabilities", None) or [])
    if not caps:
        return None
    blocked = frozenset(SCHEDULE_AGENT_TOOL_NAMES)
    return [name for name in caps if name not in blocked]


def effective_scheduled_task_tool_names(task) -> list[str]:
    """Legacy concrete tool list; scheduled fire path no longer uses this."""
    resolved = resolve_scheduled_task_capabilities(task)
    if resolved is None:
        return selectable_scheduled_task_tool_names()
    return resolved


def _html_comment_safe(text: str) -> str:
    """Avoid terminating an HTML comment early (`--` is illegal inside comments)."""
    return (text or "").replace("--", "—")


def infer_schedule_ui_language(*parts: str | None) -> str:
    """
    Best-effort UI language for the short visible scheduled-task label.

    User language is frontend-only today, so infer from title/instruction text.
    """
    sample = " ".join(p for p in parts if p).lower()
    if not sample.strip():
        return "en"
    spanish_markers = (
        "ción",
        "ñ",
        "á",
        "é",
        "í",
        "ó",
        "ú",
        "¿",
        "¡",
        " que ",
        " para ",
        " con ",
        " una ",
        " los ",
        " las ",
        " del ",
        " usa ",
        " genera ",
        " envía ",
        " enviar ",
        " crear ",
        " revisa ",
        " pedir ",
        " permiso ",
    )
    score = sum(1 for marker in spanish_markers if marker in sample)
    return "es" if score >= 2 else "en"


def format_scheduled_task_visible_label(title: str, language: str) -> str:
    clean_title = (title or "").strip() or (
        "Tarea sin título" if language == "es" else "Untitled task"
    )
    if language == "es":
        return f"Ejecutando tarea: {clean_title}"
    return f"Executing task: {clean_title}"


def build_scheduled_task_execution_message(task: Any) -> str:
    """
    Build the user-message text injected when a scheduled task fires.

    Visible line is a short localized label; full execution context lives in an
    HTML comment so Markdown UIs (skipHtml) hide it while the model still sees it.
    """
    schedule_type = getattr(task, "schedule_type", None) or "once"
    kind = "recurring" if schedule_type == "recurring" else "one-off"
    title = (getattr(task, "title", None) or "").strip() or "(untitled)"
    tz_name = getattr(task, "timezone", None) or "UTC"
    instruction = (getattr(task, "instruction_text", None) or "").strip()
    summary = format_schedule_summary(
        schedule_type=schedule_type,
        tz_name=tz_name,
        next_run_at_utc=getattr(task, "next_run_at", None)
        or datetime.now(ZoneInfo("UTC")),
        recurrence=getattr(task, "recurrence", None),
        time_of_day=getattr(task, "time_of_day", None),
        weekdays=getattr(task, "weekdays", None) or [],
        day_of_month=getattr(task, "day_of_month", None),
        cron=getattr(task, "cron", None),
    )
    explicit_caps = resolve_scheduled_task_capabilities(task)
    if explicit_caps is None:
        caps_line = (
            "each agent's pre_approved_tools (plus server auto-injection; "
            "no shared schedule allowlist)"
        )
    else:
        # Legacy tasks that still have a capabilities snapshot in the DB.
        caps_line = ", ".join(explicit_caps) if explicit_caps else "(none)"

    next_run = getattr(task, "next_run_at", None)
    next_local = None
    if next_run is not None:
        if getattr(next_run, "tzinfo", None) is None:
            from django.utils import timezone as dj_tz

            next_run = dj_tz.make_aware(next_run, ZoneInfo("UTC"))
        next_local = local_iso_from_utc(next_run, tz_name)

    language = infer_schedule_ui_language(title, instruction)
    visible = format_scheduled_task_visible_label(title, language)

    detail_lines = [
        "SCHEDULED_TASK_EXECUTION",
        (
            f"You are running a {kind} scheduled task for this conversation. "
            "This is an automatic execution, not a live user request to schedule work."
        ),
        "Do NOT create, list, or cancel schedules on this turn. Scheduling tools are unavailable.",
        "Execute the step-by-step plan below end-to-end using the available tools.",
        "If a step cannot be completed (missing tool, auth, or data), report that limitation clearly and continue with the rest.",
        "When finished, summarize what you completed and what remains blocked.",
        "",
        f"Title: {title}",
        f"Task ID: {task.id}",
        f"Schedule type: {schedule_type}",
        f"Schedule: {summary}",
        f"Timezone: {tz_name}",
    ]
    if next_local:
        detail_lines.append(f"Current run local time: {next_local}")
    detail_lines.extend(
        [
            f"Available tools for this run: {caps_line}",
            "",
            "Step-by-step execution plan:",
            instruction or "(no steps provided)",
            "END_SCHEDULED_TASK_EXECUTION",
        ]
    )
    comment_body = _html_comment_safe("\n".join(detail_lines))
    return f"{visible}\n\n<!--\n{comment_body}\n-->"


# Small epsilon used when advancing recurring schedules after a run.
RECURRING_ADVANCE_EPSILON = timedelta(seconds=1)
