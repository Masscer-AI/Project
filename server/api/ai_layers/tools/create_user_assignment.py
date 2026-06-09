"""
Create a UserAssignment workflow (checklist) for the current user.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from api.assignments.actions import create_user_assignment as create_assignment_impl
from api.assignments.schemas import StepStatus, validate_assignment_metadata


# Use Literal instead of Enum so Pydantic emits an inline list of values in
# the JSON schema rather than a $ref. OpenAI rejects $ref when it carries
# sibling keywords like "description" or "default".
class CreateAssignmentStepButtonParam(BaseModel):
    text: str = Field(min_length=1, description="Button label, e.g. 'Open members'")
    action_type: Literal["navigate", "focus_element", "none"] = "navigate"
    action_target: Optional[str] = Field(
        default=None,
        description=(
            "For navigate: a navigate_targets key (e.g. organization_members) or path. "
            "For focus_element: a focus_targets key. See read_masscer_instructions."
        ),
    )


class CreateAssignmentStepParam(BaseModel):
    title: str = Field(min_length=1, description="Step title shown in the checklist")
    description: str = Field(default="", description="Optional short description")
    route: Optional[str] = Field(
        default=None,
        description="Optional page where the action happens (auto-filled from catalog).",
    )
    button: Optional[CreateAssignmentStepButtonParam] = Field(
        default=None,
        description="Optional action button (call read_masscer_instructions first).",
    )
    app_url: Optional[str] = Field(
        default=None,
        description="Deprecated: bare frontend path. Prefer 'button' with action_target.",
    )
    help_topic_id: Optional[str] = Field(
        default=None,
        description="Optional Masscer help topic id for reference",
    )


class CreateUserAssignmentParams(BaseModel):
    title: str = Field(min_length=1, description="Assignment / workflow title")
    steps: list[CreateAssignmentStepParam] = Field(
        min_length=1,
        description="Ordered checklist steps (at least one)",
    )


class CreateUserAssignmentStepResult(BaseModel):
    id: str
    title: str
    status: str


class CreateUserAssignmentResult(BaseModel):
    id: str
    title: str
    steps: list[CreateUserAssignmentStepResult]
    message: str = "Assignment created successfully"


def _create_user_assignment_impl(
    title: str,
    steps: list[dict],
    *,
    user_id: int,
    organization_id=None,
) -> CreateUserAssignmentResult:
    assignment = create_assignment_impl(
        user_id=user_id,
        title=title,
        steps=steps,
        organization_id=organization_id,
        key=None,
    )
    meta = validate_assignment_metadata(assignment.metadata)
    return CreateUserAssignmentResult(
        id=str(assignment.id),
        title=assignment.title,
        steps=[
            CreateUserAssignmentStepResult(
                id=s.id,
                title=s.title,
                status=s.status.value if isinstance(s.status, StepStatus) else str(s.status),
            )
            for s in meta.steps
        ],
    )


def get_tool(
    user_id: int | None = None,
    organization_id=None,
    **kwargs,
) -> dict:
    if not user_id:
        raise ValueError("create_user_assignment requires user_id in tool context")

    def create_user_assignment(
        title: str, steps: list[dict]
    ) -> CreateUserAssignmentResult:
        return _create_user_assignment_impl(
            title,
            steps,
            user_id=user_id,
            organization_id=organization_id,
        )

    return {
        "name": "create_user_assignment",
        "description": (
            "Create a checklist-style assignment for the current user with ordered steps. "
            "Use when the user asks how to do something multi-step in Masscer — "
            "answer in chat AND optionally assign a workflow they can track in the Tasks panel. "
            "Each step needs a title; add a button with an action_target from "
            "read_masscer_instructions (navigate or focus_element). Do not invent flows."
        ),
        "parameters": CreateUserAssignmentParams,
        "function": create_user_assignment,
    }
