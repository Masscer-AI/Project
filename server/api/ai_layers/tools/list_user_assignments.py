"""
List active UserAssignment workflows for the current user.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from api.assignments.models import AssignmentStatus, UserAssignment
from api.assignments.schemas import StepStatus, validate_assignment_metadata


class ListUserAssignmentsParams(BaseModel):
    pass


class ListUserAssignmentStepSummary(BaseModel):
    id: str
    title: str
    status: str


class ListUserAssignmentItem(BaseModel):
    id: str
    title: str
    status: str
    progress: float
    steps: list[ListUserAssignmentStepSummary]


class ListUserAssignmentsResult(BaseModel):
    assignments: list[ListUserAssignmentItem] = Field(default_factory=list)


def _list_user_assignments_impl(user_id: int) -> ListUserAssignmentsResult:
    qs = (
        UserAssignment.objects.filter(user_id=user_id)
        .exclude(status=AssignmentStatus.ARCHIVED)
        .order_by("-created_at")[:20]
    )
    items: list[ListUserAssignmentItem] = []
    for a in qs:
        meta = validate_assignment_metadata(a.metadata)
        items.append(
            ListUserAssignmentItem(
                id=str(a.id),
                title=a.title,
                status=a.status,
                progress=meta.progress,
                steps=[
                    ListUserAssignmentStepSummary(
                        id=s.id,
                        title=s.title,
                        status=s.status.value
                        if isinstance(s.status, StepStatus)
                        else str(s.status),
                    )
                    for s in meta.steps
                ],
            )
        )
    return ListUserAssignmentsResult(assignments=items)


def get_tool(user_id: int | None = None, **kwargs) -> dict:
    if not user_id:
        raise ValueError("list_user_assignments requires user_id in tool context")

    def list_user_assignments() -> ListUserAssignmentsResult:
        return _list_user_assignments_impl(user_id)

    return {
        "name": "list_user_assignments",
        "description": (
            "List the current user's active assignments (checklists) with step progress. "
            "Use before creating a duplicate workflow."
        ),
        "parameters": ListUserAssignmentsParams,
        "function": list_user_assignments,
    }
