"""
Tool: schedule_task

Schedule a one-off or recurring agent turn in a conversation. The instruction is
stored and later injected as a user message that re-enters conversation_agent_task.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ScheduleTaskParams(BaseModel):
    instruction: str = Field(
        description=(
            "Self-contained imperative task written as a future user message "
            "(second person / command form). Example: 'Write a competitor report "
            "covering the last week as a docx and email it to all organization members.' "
            "Do not write as an assistant reply."
        ),
    )
    schedule_type: Literal["once", "recurring"] = Field(
        description="once for a single future run; recurring for repeating runs.",
    )
    run_at: str | None = Field(
        default=None,
        description=(
            "Required for once. Local wall time YYYY-MM-DDTHH:MM:SS in the organization "
            "timezone, or RFC3339 with offset."
        ),
    )
    recurrence: Literal["daily", "weekly", "monthly"] | None = Field(
        default=None,
        description="Required for recurring unless cron is provided.",
    )
    time_of_day: str | None = Field(
        default=None,
        description="Local HH:MM (24h) in organization timezone for structured recurrence.",
    )
    weekdays: list[int] | None = Field(
        default=None,
        description="For weekly recurrence: 0=Monday … 6=Sunday.",
    )
    day_of_month: int | None = Field(
        default=None,
        description="For monthly recurrence: day of month 1-31.",
    )
    cron: str | None = Field(
        default=None,
        description=(
            "Optional 5-field cron (minute hour day month weekday) interpreted in the "
            "organization timezone. Prefer structured recurrence fields when possible."
        ),
    )


class ScheduleTaskResult(BaseModel):
    success: bool
    message: str
    task_id: str | None = None
    timezone: str | None = None
    next_run_at_local: str | None = None
    next_run_at_utc: str | None = None
    schedule_summary: str | None = None


def _schedule_task_impl(
    *,
    instruction: str,
    schedule_type: Literal["once", "recurring"],
    conversation_id: str,
    organization_id: int,
    user_id: int,
    agent_slugs: list[str] | None,
    multiagentic_modality: str,
    run_at: str | None = None,
    recurrence: Literal["daily", "weekly", "monthly"] | None = None,
    time_of_day: str | None = None,
    weekdays: list[int] | None = None,
    day_of_month: int | None = None,
    cron: str | None = None,
) -> ScheduleTaskResult:
    from api.ai_layers.tools.calendar_tool_helpers import resolve_org_timezone
    from api.messaging.models import Conversation, ScheduledConversationTask
    from api.messaging.schedule_helpers import (
        compute_next_run_at,
        parse_run_at_to_utc,
        resolve_cron_expression,
        schedule_payload_dict,
    )
    from api.messaging.tasks import enqueue_scheduled_conversation_task
    from django.contrib.auth.models import User

    instruction = (instruction or "").strip()
    if not instruction:
        raise ValueError("instruction is required.")

    try:
        conversation = Conversation.objects.select_related("organization").get(
            id=conversation_id
        )
    except Conversation.DoesNotExist as exc:
        raise ValueError("Conversation not found.") from exc

    # Web chats often leave Conversation.organization_id null; the agent task then
    # resolves org from the user/agent. Only reject when the conversation is tied
    # to a *different* org than the tool context.
    if (
        conversation.organization_id is not None
        and conversation.organization_id != organization_id
    ):
        raise ValueError("Conversation does not belong to this organization.")

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist as exc:
        raise ValueError("Authenticated user not found.") from exc

    tz_name = resolve_org_timezone(organization_id)
    run_at_utc = None
    cron_expr = None

    if schedule_type == "once":
        if not run_at:
            raise ValueError("once schedules require run_at.")
        run_at_utc = parse_run_at_to_utc(run_at, tz_name)
        next_run = compute_next_run_at(
            schedule_type="once",
            tz_name=tz_name,
            run_at_utc=run_at_utc,
        )
    else:
        cron_expr = resolve_cron_expression(
            schedule_type="recurring",
            recurrence=recurrence,
            time_of_day=time_of_day,
            weekdays=weekdays,
            day_of_month=day_of_month,
            cron=cron,
        )
        next_run = compute_next_run_at(
            schedule_type="recurring",
            tz_name=tz_name,
            cron=cron_expr,
        )

    slugs = [str(s) for s in (agent_slugs or []) if s]
    task = ScheduledConversationTask.objects.create(
        conversation=conversation,
        organization_id=organization_id,
        created_by=user,
        instruction_text=instruction,
        schedule_type=schedule_type,
        timezone=tz_name,
        run_at=run_at_utc,
        recurrence=recurrence if schedule_type == "recurring" else None,
        time_of_day=time_of_day if schedule_type == "recurring" else None,
        weekdays=list(weekdays or []) if schedule_type == "recurring" else [],
        day_of_month=day_of_month if schedule_type == "recurring" else None,
        cron=cron_expr,
        next_run_at=next_run,
        status=ScheduledConversationTask.Status.PENDING,
        agent_slugs=slugs,
        multiagentic_modality=multiagentic_modality or "isolated",
    )
    enqueue_scheduled_conversation_task(task)
    payload = schedule_payload_dict(task)
    logger.info(
        "Scheduled conversation task created id=%s conversation=%s next=%s",
        task.id,
        conversation_id,
        payload.get("next_run_at_local"),
    )
    return ScheduleTaskResult(
        success=True,
        message="Scheduled task created.",
        task_id=str(task.id),
        timezone=tz_name,
        next_run_at_local=payload.get("next_run_at_local"),
        next_run_at_utc=payload.get("next_run_at_utc"),
        schedule_summary=payload.get("schedule_summary"),
    )


def get_tool(
    conversation_id: str | None = None,
    organization_id: int | None = None,
    user_id: int | None = None,
    agent_slugs: list[str] | None = None,
    multiagentic_modality: str = "isolated",
    **kwargs,
) -> dict:
    if not conversation_id:
        raise ValueError("schedule_task requires conversation_id in context")
    if organization_id is None:
        raise ValueError("schedule_task requires organization_id in context")
    if user_id is None:
        raise ValueError("schedule_task requires user_id in context")

    from api.ai_layers.tools.calendar_tool_helpers import resolve_org_timezone

    tz_name = resolve_org_timezone(organization_id)
    tz_line = (
        f"Organization timezone for task scheduling: {tz_name}. "
        "Use this timezone for run_at and recurrence wall times unless an offset is provided."
    )

    def schedule_task(
        instruction: str,
        schedule_type: Literal["once", "recurring"],
        run_at: str | None = None,
        recurrence: Literal["daily", "weekly", "monthly"] | None = None,
        time_of_day: str | None = None,
        weekdays: list[int] | None = None,
        day_of_month: int | None = None,
        cron: str | None = None,
    ) -> ScheduleTaskResult:
        return _schedule_task_impl(
            instruction=instruction,
            schedule_type=schedule_type,
            conversation_id=conversation_id,
            organization_id=organization_id,
            user_id=user_id,
            agent_slugs=agent_slugs,
            multiagentic_modality=multiagentic_modality,
            run_at=run_at,
            recurrence=recurrence,
            time_of_day=time_of_day,
            weekdays=weekdays,
            day_of_month=day_of_month,
            cron=cron,
        )

    return {
        "name": "schedule_task",
        "description": (
            "Schedule a one-off or recurring task that will later run in this conversation "
            "as a user message (the full agent with tools will execute it). "
            "Write instruction as a self-contained imperative user task, not as an assistant reply. "
            f"{tz_line} "
            "All schedule wall times use the organization timezone unless run_at includes an offset. "
            "For recurring, prefer recurrence + time_of_day (+ weekdays/day_of_month); cron is optional."
        ),
        "parameters": ScheduleTaskParams,
        "function": schedule_task,
    }
