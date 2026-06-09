"""
Built-in assignment templates (seeded for specific user roles).
"""

from __future__ import annotations

from api.assignments.schemas import (
    AssignmentStepInput,
    StepActionType,
    StepButtonInput,
    build_metadata_from_steps,
)

OWNER_ONBOARDING_KEY = "owner_onboarding"
OWNER_ONBOARDING_TITLE = "Get started with Masscer"

OWNER_ONBOARDING_STEPS: list[AssignmentStepInput] = [
    AssignmentStepInput(
        id="invite_user",
        title="Invite your team",
        description="Add members to your organization by email.",
        help_topic_id="invite_user",
        button=StepButtonInput(
            text="Open members",
            action_type=StepActionType.navigate,
            action_target="organization_members",
        ),
    ),
    AssignmentStepInput(
        id="create_agent",
        title="Create your first AI agent",
        description="Open the agents modal from the chat header to manage your agents.",
        help_topic_id="create_agent",
        button=StepButtonInput(
            text="Highlight agents button",
            action_type=StepActionType.focus_element,
            action_target="agents-modal-trigger",
        ),
    ),
    AssignmentStepInput(
        id="knowledge_base",
        title="Train agents with your knowledge",
        description="Upload documents and link them to your agents.",
        help_topic_id="knowledge_base",
        button=StepButtonInput(
            text="Open knowledge base",
            action_type=StepActionType.navigate,
            action_target="knowledge_base",
        ),
    ),
]


def owner_onboarding_metadata() -> dict:
    return build_metadata_from_steps(OWNER_ONBOARDING_STEPS)
