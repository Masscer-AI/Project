from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from api.compliance.risk.catalog import RISK_GATE_VERSION

Semaphore = Literal["green", "yellow", "orange", "red"]
DiligenceLevel = Literal[1, 2, 3]
RecommendedAction = Literal[
    "alta",
    "alta_condicionada",
    "requerimiento",
    "edd",
    "escalamiento",
]
ScreeningClass = Literal["none", "possible", "discarded", "confirmed"]


class RiskGateResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ruleset_version: str = RISK_GATE_VERSION
    semaphore: Semaphore
    diligence_level: DiligenceLevel
    recommended_action: RecommendedAction
    reasons: list[str] = Field(default_factory=list)
    screening_class: ScreeningClass = "none"
    fiscal_list_kind: str = ""
    ready_for_signature: bool = False
    invitee_summary: str = ""
