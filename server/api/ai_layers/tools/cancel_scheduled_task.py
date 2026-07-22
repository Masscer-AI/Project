"""
Tool: cancel_scheduled_task

Cancel a pending/running scheduled conversation task in the current conversation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from api.messaging.schedule_service import ScheduleServiceError, cancel_scheduled_task


class CancelScheduledTaskParams(BaseModel):
    task_id: str = Field(description="UUID of the scheduled task to cancel.")


class CancelScheduledTaskResult(BaseModel):
    success: bool
    message: str
    task_id: str | None = None
    status: str | None = None


def _cancel_scheduled_task_impl(
    *,
    task_id: str,
    conversation_id: str,
    organization_id: int,
) -> CancelScheduledTaskResult:
    try:
        result = cancel_scheduled_task(
            task_id=task_id,
            conversation_id=conversation_id,
            organization_id=organization_id,
        )
    except ScheduleServiceError as exc:
        raise ValueError(exc.message) from exc
    return CancelScheduledTaskResult(**result)


def get_tool(
    conversation_id: str | None = None,
    organization_id: int | None = None,
    **kwargs,
) -> dict:
    if not conversation_id:
        raise ValueError("cancel_scheduled_task requires conversation_id in context")
    if organization_id is None:
        raise ValueError("cancel_scheduled_task requires organization_id in context")

    def cancel_scheduled_task_tool(task_id: str) -> CancelScheduledTaskResult:
        return _cancel_scheduled_task_impl(
            task_id=task_id,
            conversation_id=conversation_id,
            organization_id=organization_id,
        )

    return {
        "name": "cancel_scheduled_task",
        "description": (
            "Cancel a pending or running scheduled task in this conversation by task_id. "
            "Use list_scheduled_tasks to find ids."
        ),
        "parameters": CancelScheduledTaskParams,
        "function": cancel_scheduled_task_tool,
    }
