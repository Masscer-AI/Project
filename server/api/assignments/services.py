from __future__ import annotations

from django.utils import timezone

from api.assignments.models import AssignmentStatus, UserAssignment
from api.assignments.schemas import AssignmentMetadata, StepStatus, metadata_to_json


def recalculate_assignment_status(meta: AssignmentMetadata) -> AssignmentStatus:
    if not meta.steps:
        return AssignmentStatus.PENDING
    statuses = {s.status for s in meta.steps}
    if all(s.status == StepStatus.done for s in meta.steps):
        return AssignmentStatus.DONE
    if StepStatus.in_progress in statuses or StepStatus.done in statuses:
        return AssignmentStatus.IN_PROGRESS
    return AssignmentStatus.PENDING


def update_assignment_step_status(
    assignment: UserAssignment,
    step_id: str,
    new_status: str,
) -> UserAssignment:
    meta = assignment.parsed_metadata()
    step = next((s for s in meta.steps if s.id == step_id), None)
    if not step:
        raise ValueError(f"Unknown step_id '{step_id}'")

    try:
        status_enum = StepStatus(new_status)
    except ValueError as exc:
        raise ValueError(
            f"Invalid status '{new_status}'. Must be one of: pending, in_progress, done"
        ) from exc

    step.status = status_enum
    if status_enum == StepStatus.done:
        step.completed_at = timezone.now()
    elif status_enum == StepStatus.pending:
        step.completed_at = None

    assignment.metadata = metadata_to_json(meta)
    assignment.status = recalculate_assignment_status(meta)
    if assignment.status == AssignmentStatus.DONE:
        assignment.completed_at = timezone.now()
    elif assignment.status != AssignmentStatus.DONE:
        assignment.completed_at = None

    assignment.save()
    return assignment


def archive_assignment(assignment: UserAssignment) -> UserAssignment:
    assignment.status = AssignmentStatus.ARCHIVED
    assignment.save(update_fields=["status", "updated_at"])
    return assignment
