from __future__ import annotations

from api.assignments.models import UserAssignment
from api.assignments.schemas import validate_assignment_metadata


def serialize_assignment(assignment: UserAssignment) -> dict:
    meta = validate_assignment_metadata(assignment.metadata)
    return {
        "id": str(assignment.id),
        "key": assignment.key,
        "title": assignment.title,
        "status": assignment.status,
        "organization_id": str(assignment.organization_id)
        if assignment.organization_id
        else None,
        "metadata": meta.model_dump(mode="json"),
        "progress": meta.progress,
        "completed_at": assignment.completed_at.isoformat()
        if assignment.completed_at
        else None,
        "created_at": assignment.created_at.isoformat(),
        "updated_at": assignment.updated_at.isoformat(),
    }
