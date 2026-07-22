"""
Shared list/cancel logic for ScheduledConversationTask (agent tools + REST).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ScheduleServiceError(Exception):
    """Raised for not-found / invalid cancel operations."""

    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


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

    return {
        "success": True,
        "timezone": tz_name,
        "tasks": tasks,
        "count": len(tasks),
    }


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
    ).select_related("conversation")

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
    tz_name = tasks[0].get("timezone") if tasks else "UTC"
    return {
        "success": True,
        "timezone": tz_name or "UTC",
        "tasks": tasks,
        "count": len(tasks),
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
