from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from api.compliance.clarifications import InviteeRequestSpec


class ScreeningSearch(BaseModel):
    model_config = ConfigDict(extra="ignore")

    terms: list[str] = Field(default_factory=list)
    lists: list[str] = Field(default_factory=list)
    hit_count: int = 0


class ScreeningHit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    list_slug: str
    reference_number: str
    primary_name: str
    strength: Literal["none", "weak", "strong", "exact"] = "weak"
    notes: str | None = None
    situation: str = ""


class ScreeningResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    verdict: Literal[
        "clear",
        "needs_invitee_input",
        "human_review",
        "escalate",
    ]
    summary: str
    hits: list[ScreeningHit] = Field(default_factory=list)
    queries_run: list[str] = Field(default_factory=list)
    searches: list[ScreeningSearch] = Field(default_factory=list)
    invitee_requests: list[InviteeRequestSpec] = Field(default_factory=list)
    human_notes: str | None = None
