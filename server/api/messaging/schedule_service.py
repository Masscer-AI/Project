"""
Shared list/cancel/update logic for ScheduledConversationTask (agent tools + REST).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ScheduleServiceError(Exception):
    """Raised for not-found / invalid cancel/update operations."""

    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _list_envelope(tasks: list[dict[str, Any]], timezone: str) -> dict[str, Any]:
    from api.messaging.schedule_helpers import selectable_scheduled_task_tool_names

    return {
        "success": True,
        "timezone": timezone,
        "tasks": tasks,
        "count": len(tasks),
        "available_tools": selectable_scheduled_task_tool_names(),
    }


def list_scheduled_tasks_for_conversation(
    *,
    conversation_id: str,
    organization_id: int | None = None,
    include_finished: bool = False,
    limit: int = 20,
) -> dict[str, Any]:
    from api.ai_layers.tools.calendar_tool_helpers import resolve_org_timezone
    from api.messaging.models import ScheduledConversationTask
    from api.messaging.schedule_helpers import schedule_payload_dict

    limit = max(1, min(int(limit), 100))
    qs = ScheduledConversationTask.objects.filter(
        conversation_id=conversation_id
    ).select_related("conversation")
    if organization_id is not None:
        qs = qs.filter(organization_id=organization_id)

    if not include_finished:
        qs = qs.filter(
            status__in=[
                ScheduledConversationTask.Status.PENDING,
                ScheduledConversationTask.Status.RUNNING,
            ]
        )
        qs = qs.order_by("next_run_at", "-created_at")
    else:
        qs = qs.order_by("-created_at")

    tasks = [schedule_payload_dict(t) for t in qs[:limit]]
    tz_name = resolve_org_timezone(organization_id) if organization_id is not None else "UTC"
    if organization_id is None and tasks:
        tz_name = tasks[0].get("timezone") or tz_name

    return _list_envelope(tasks, tz_name)


def list_scheduled_tasks_for_user(
    *,
    user_id: int,
    include_finished: bool = False,
    limit: int = 50,
) -> dict[str, Any]:
    """List scheduled tasks created by the given user across conversations."""
    from api.messaging.models import ScheduledConversationTask
    from api.messaging.schedule_helpers import schedule_payload_dict

    limit = max(1, min(int(limit), 100))
    qs = ScheduledConversationTask.objects.filter(
        created_by_id=user_id
    ).select_related("conversation").exclude(
        status=ScheduledConversationTask.Status.CANCELLED,
    )

    if not include_finished:
        qs = qs.filter(
            status__in=[
                ScheduledConversationTask.Status.PENDING,
                ScheduledConversationTask.Status.RUNNING,
            ]
        )
        qs = qs.order_by("next_run_at", "-created_at")
    else:
        # "Show finished" means completed/failed — never cancelled.
        qs = qs.order_by("-created_at")

    tasks = [schedule_payload_dict(t) for t in qs[:limit]]
    tz_name = tasks[0].get("timezone") if tasks else "UTC"
    return _list_envelope(tasks, tz_name or "UTC")


def update_scheduled_task_capabilities(
    *,
    task_id: str,
    capabilities: list[str] | None,
    conversation_id: str | None = None,
    organization_id: int | None = None,
    user_id: int | None = None,
) -> dict[str, Any]:
    """Replace the tool allowlist for a pending/running scheduled task."""
    from api.ai_layers.tools import SCHEDULE_AGENT_TOOL_NAMES
    from api.messaging.models import ScheduledConversationTask
    from api.messaging.schedule_helpers import (
        normalize_capability_names,
        schedule_payload_dict,
        selectable_scheduled_task_tool_names,
    )

    filters: dict[str, Any] = {"id": task_id}
    if conversation_id is not None:
        filters["conversation_id"] = conversation_id
    if organization_id is not None:
        filters["organization_id"] = organization_id
    if user_id is not None:
        filters["created_by_id"] = user_id

    try:
        task = ScheduledConversationTask.objects.select_related("conversation").get(
            **filters
        )
    except (ScheduledConversationTask.DoesNotExist, ValueError, TypeError) as exc:
        raise ScheduleServiceError(
            "Scheduled task not found.",
            status_code=404,
        ) from exc

    if task.status not in (
        ScheduledConversationTask.Status.PENDING,
        ScheduledConversationTask.Status.RUNNING,
    ):
        raise ScheduleServiceError(
            f"Cannot update tools for a task with status {task.status}.",
            status_code=400,
        )

    if capabilities is None:
        raise ScheduleServiceError("capabilities must be a list of tool names.")

    if not isinstance(capabilities, list):
        raise ScheduleServiceError("capabilities must be a list of tool names.")

    selectable = set(selectable_scheduled_task_tool_names())
    blocked = frozenset(SCHEDULE_AGENT_TOOL_NAMES)
    unknown: list[str] = []
    for item in capabilities:
        if not isinstance(item, str):
            raise ScheduleServiceError("Each capability must be a string tool name.")
        name = item.strip()
        if not name:
            continue
        if name in blocked:
            raise ScheduleServiceError(
                f"Schedule-management tool '{name}' cannot be assigned to a task."
            )
        if name not in selectable:
            unknown.append(name)
    if unknown:
        raise ScheduleServiceError(
            f"Unknown tools: {', '.join(sorted(set(unknown)))}."
        )

    normalized = [
        name
        for name in normalize_capability_names(capabilities)
        if name not in blocked
    ]
    task.capabilities = normalized
    task.save(update_fields=["capabilities", "updated_at"])
    logger.info(
        "Updated scheduled task capabilities id=%s tools=%s",
        task.id,
        normalized or "ALL",
    )
    return {
        "success": True,
        "message": "Scheduled task tools updated.",
        "task": schedule_payload_dict(task),
        "available_tools": selectable_scheduled_task_tool_names(),
    }


def cancel_scheduled_task(
    *,
    task_id: str,
    conversation_id: str | None = None,
    organization_id: int | None = None,
) -> dict[str, Any]:
    from api.messaging.models import ScheduledConversationTask

    filters: dict[str, Any] = {"id": task_id}
    if conversation_id is not None:
        filters["conversation_id"] = conversation_id
    if organization_id is not None:
        filters["organization_id"] = organization_id

    try:
        task = ScheduledConversationTask.objects.select_related("conversation").get(
            **filters
        )
    except (ScheduledConversationTask.DoesNotExist, ValueError, TypeError) as exc:
        raise ScheduleServiceError(
            "Scheduled task not found in this conversation.",
            status_code=404,
        ) from exc

    if task.status == ScheduledConversationTask.Status.CANCELLED:
        return {
            "success": True,
            "message": "Task was already cancelled.",
            "task_id": str(task.id),
            "status": task.status,
        }
    if task.status in (
        ScheduledConversationTask.Status.DONE,
        ScheduledConversationTask.Status.FAILED,
    ):
        return {
            "success": False,
            "message": f"Cannot cancel a task with status {task.status}.",
            "task_id": str(task.id),
            "status": task.status,
        }

    celery_id = (task.celery_task_id or "").strip()
    if celery_id:
        try:
            from api.celery import app as celery_app

            celery_app.control.revoke(celery_id, terminate=False)
        except Exception:
            logger.warning(
                "Failed to revoke celery task %s for scheduled task %s",
                celery_id,
                task.id,
                exc_info=True,
            )

    task.status = ScheduledConversationTask.Status.CANCELLED
    task.celery_task_id = None
    task.save(update_fields=["status", "celery_task_id", "updated_at"])
    logger.info(
        "Cancelled scheduled conversation task id=%s conversation=%s",
        task.id,
        task.conversation_id,
    )
    return {
        "success": True,
        "message": "Scheduled task cancelled.",
        "task_id": str(task.id),
        "status": task.status,
    }
