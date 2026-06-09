"""
Return the catalog of valid onboarding actions (navigate / focus targets).

The platform assistant MUST call this before building assignment step buttons,
so it only uses flows that actually exist (no hallucinated pages/actions).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from api.assignments.onboarding_actions import onboarding_actions_catalog


class ReadMasscerInstructionsParams(BaseModel):
    pass


class NavigateTargetItem(BaseModel):
    key: str
    path: str
    description: str


class FocusTargetItem(BaseModel):
    key: str
    route: str
    description: str


class ReadMasscerInstructionsResult(BaseModel):
    navigate_targets: list[NavigateTargetItem] = Field(default_factory=list)
    focus_targets: list[FocusTargetItem] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)


_RULES = [
    "Step buttons may use ONLY the action targets listed here. Never invent routes, "
    "selectors, or flows.",
    "action_type 'navigate': action_target must be a navigate_targets key (preferred) "
    "or an absolute path starting with '/'.",
    "action_type 'focus_element': action_target must be a focus_targets key; the panel "
    "scrolls to and highlights that element.",
    "action_type 'none': informational step with no button action.",
    "Viewing invoices/billing history is NOT available yet — do not create such steps.",
    "Keep each step to a single concrete action; split multi-action guidance into "
    "multiple steps.",
]


def _read_masscer_instructions_impl() -> ReadMasscerInstructionsResult:
    catalog = onboarding_actions_catalog()
    return ReadMasscerInstructionsResult(
        navigate_targets=[NavigateTargetItem(**n) for n in catalog["navigate_targets"]],
        focus_targets=[FocusTargetItem(**f) for f in catalog["focus_targets"]],
        rules=_RULES,
    )


def get_tool(**kwargs) -> dict:
    def read_masscer_instructions() -> ReadMasscerInstructionsResult:
        return _read_masscer_instructions_impl()

    return {
        "name": "read_masscer_instructions",
        "description": (
            "Read the catalog of valid onboarding actions (navigate targets, focus "
            "targets) and authoring rules. Call this BEFORE create_user_assignment "
            "whenever steps need buttons, to avoid inventing flows that don't exist."
        ),
        "parameters": ReadMasscerInstructionsParams,
        "function": read_masscer_instructions,
    }
