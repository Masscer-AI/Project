"""
Tool: list_scheduled_tasks

List scheduled conversation tasks for the current conversation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from api.messaging.schedule_service import list_scheduled_tasks_for_conversation


class ListScheduledTasksParams(BaseModel):
    include_finished: bool = Field(
        default=False,
        description="If true, also include done/cancelled/failed tasks (most recent first).",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Max number of tasks to return.",
    )


class ListScheduledTasksResult(BaseModel):
    success: bool
    timezone: str
    tasks: list[dict]
    count: int


def _list_scheduled_tasks_impl(
    *,
    conversation_id: str,
    organization_id: int,
    include_finished: bool = False,
    limit: int = 20,
) -> ListScheduledTasksResult:
    result = list_scheduled_tasks_for_conversation(
        conversation_id=conversation_id,
        organization_id=organization_id,
        include_finished=include_finished,
        limit=limit,
    )
    return ListScheduledTasksResult(**result)


def get_tool(
    conversation_id: str | None = None,
    organization_id: int | None = None,
    **kwargs,
) -> dict:
    if not conversation_id:
        raise ValueError("list_scheduled_tasks requires conversation_id in context")
    if organization_id is None:
        raise ValueError("list_scheduled_tasks requires organization_id in context")

    def list_scheduled_tasks(
        include_finished: bool = False,
        limit: int = 20,
    ) -> ListScheduledTasksResult:
        return _list_scheduled_tasks_impl(
            conversation_id=conversation_id,
            organization_id=organization_id,
            include_finished=include_finished,
            limit=limit,
        )

    return {
        "name": "list_scheduled_tasks",
        "description": (
            "List scheduled tasks for this conversation (pending/running by default). "
            "Use before cancel_scheduled_task to find task ids. "
            "Times are shown in the organization timezone."
        ),
        "parameters": ListScheduledTasksParams,
        "function": list_scheduled_tasks,
    }
