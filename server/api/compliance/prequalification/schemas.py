"""Structured result of identification pre-qualification (before list screening)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PrequalFinding(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str
    severity: Literal["blocker", "warning", "info"]
    target: str | None = None
    summary: str
    evidence: str | None = None
    source_ids: list[str] = Field(default_factory=list)


class PrequalificationResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ruleset_version: str
    verdict: Literal["ready_for_list_screening", "needs_review", "blocked"]
    summary: str
    findings: list[PrequalFinding] = Field(default_factory=list)
    controllers: list[str] = Field(default_factory=list)
    human_notes: str | None = None
