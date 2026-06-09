"""
Pydantic schemas for UserAssignment.metadata.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from django.utils.text import slugify
from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.assignments.onboarding_actions import (
    is_valid_focus_target,
    is_valid_navigate_target,
    resolve_focus_route,
    resolve_navigate_path,
)


class StepStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    done = "done"


class StepActionType(str, Enum):
    navigate = "navigate"
    focus_element = "focus_element"
    none = "none"


class StepButton(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    action_type: StepActionType = StepActionType.navigate
    action_target: str | None = None


class AssignmentStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9_]+$")
    title: str = Field(min_length=1)
    description: str = ""
    order: int = Field(ge=1)
    status: StepStatus = StepStatus.pending
    route: str | None = None
    button: StepButton | None = None
    # Deprecated: kept for backward compatibility with early assignments.
    app_url: str | None = None
    help_topic_id: str | None = None
    completed_at: datetime | None = None


class AssignmentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1, ge=1)
    steps: list[AssignmentStep] = Field(min_length=1)

    @field_validator("steps")
    @classmethod
    def unique_step_ids(cls, v: list[AssignmentStep]) -> list[AssignmentStep]:
        ids = [s.id for s in v]
        if len(ids) != len(set(ids)):
            raise ValueError("step ids must be unique")
        return sorted(v, key=lambda s: s.order)

    @property
    def progress(self) -> float:
        if not self.steps:
            return 0.0
        done = sum(1 for s in self.steps if s.status == StepStatus.done)
        return done / len(self.steps)


class StepButtonInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    action_type: StepActionType = StepActionType.navigate
    action_target: str | None = None


class AssignmentStepInput(BaseModel):
    """Input for creating steps (tool / templates)."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    description: str = ""
    route: str | None = None
    button: StepButtonInput | None = None
    # Deprecated alias: a bare frontend path. Converted to a navigate button.
    app_url: str | None = None
    help_topic_id: str | None = None
    id: str | None = None


def _unique_step_id(base: str, used: set[str]) -> str:
    candidate = base or "step"
    if candidate not in used:
        used.add(candidate)
        return candidate
    n = 2
    while f"{candidate}_{n}" in used:
        n += 1
    final = f"{candidate}_{n}"
    used.add(final)
    return final


def _resolve_button_and_route(
    inp: AssignmentStepInput,
) -> tuple[StepButton | None, str | None, str | None]:
    """
    Resolve (button, route, app_url) for a step input.

    Validates action targets against the catalog so the assistant cannot
    invent flows. Raises ValueError on unknown targets.
    """
    button = inp.button
    route = inp.route
    app_url = inp.app_url

    # Backward-compat: a bare app_url becomes a navigate button.
    if button is None and app_url:
        button = StepButtonInput(
            text="Open page",
            action_type=StepActionType.navigate,
            action_target=app_url,
        )

    if button is None:
        return None, route, app_url

    if button.action_type == StepActionType.navigate:
        if not is_valid_navigate_target(button.action_target):
            raise ValueError(
                f"Invalid navigate action_target '{button.action_target}'. "
                "Use a key from read_masscer_instructions navigate_targets "
                "or a path starting with '/'."
            )
        resolved = resolve_navigate_path(button.action_target)
        if not route:
            route = resolved
    elif button.action_type == StepActionType.focus_element:
        if not is_valid_focus_target(button.action_target):
            raise ValueError(
                f"Invalid focus_element action_target '{button.action_target}'. "
                "Use a key from read_masscer_instructions focus_targets."
            )
        if not route:
            route = resolve_focus_route(button.action_target)

    final_button = StepButton(
        text=button.text,
        action_type=button.action_type,
        action_target=button.action_target,
    )
    return final_button, route, app_url


def build_metadata_from_steps(
    steps_input: list[AssignmentStepInput | dict],
    *,
    version: int = 1,
) -> dict:
    """Build validated metadata dict from step inputs (auto id + order)."""
    used_ids: set[str] = set()
    built_steps: list[AssignmentStep] = []

    for order, raw in enumerate(steps_input, start=1):
        inp = (
            raw
            if isinstance(raw, AssignmentStepInput)
            else AssignmentStepInput.model_validate(raw)
        )
        if inp.id:
            step_id = _unique_step_id(inp.id.strip().lower(), used_ids)
        else:
            slug = slugify(inp.title).replace("-", "_")
            if not slug:
                slug = f"step_{order}"
            step_id = _unique_step_id(slug, used_ids)

        button, route, app_url = _resolve_button_and_route(inp)

        built_steps.append(
            AssignmentStep(
                id=step_id,
                title=inp.title,
                description=inp.description,
                order=order,
                route=route,
                button=button,
                app_url=app_url,
                help_topic_id=inp.help_topic_id,
            )
        )

    meta = AssignmentMetadata(version=version, steps=built_steps)
    return meta.model_dump(mode="json")


def validate_assignment_metadata(raw: dict | None) -> AssignmentMetadata:
    return AssignmentMetadata.model_validate(raw or {"version": 1, "steps": []})


def metadata_to_json(meta: AssignmentMetadata) -> dict:
    return meta.model_dump(mode="json")
