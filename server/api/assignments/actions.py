"""
Assignment provisioning helpers.
"""

from __future__ import annotations

from typing import Optional

from api.assignments.models import AssignmentStatus, UserAssignment
from api.assignments.templates import (
    OWNER_ONBOARDING_KEY,
    OWNER_ONBOARDING_TITLE,
    owner_onboarding_metadata,
)


def ensure_owner_onboarding(
    user, organization
) -> tuple[Optional[UserAssignment], bool]:
    """
    Idempotently create the owner onboarding assignment.

    Only runs when user is the organization owner.
    Returns (assignment, created).
    """
    if organization is None or organization.owner_id != user.id:
        return None, False  # type: ignore[return-value]

    assignment, created = UserAssignment.objects.get_or_create(
        user=user,
        key=OWNER_ONBOARDING_KEY,
        defaults={
            "organization": organization,
            "title": OWNER_ONBOARDING_TITLE,
            "status": AssignmentStatus.PENDING,
            "metadata": owner_onboarding_metadata(),
        },
    )
    return assignment, created


def create_user_assignment(
    *,
    user_id: int,
    title: str,
    steps: list[dict],
    organization_id=None,
    key: str | None = None,
) -> UserAssignment:
    from api.assignments.schemas import AssignmentStepInput, build_metadata_from_steps

    step_inputs = [AssignmentStepInput.model_validate(s) for s in steps]
    metadata = build_metadata_from_steps(step_inputs)

    assignment = UserAssignment(
        user_id=user_id,
        organization_id=organization_id,
        key=key,
        title=title.strip(),
        metadata=metadata,
        status=AssignmentStatus.PENDING,
    )
    assignment.save()
    return assignment
