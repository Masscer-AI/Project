"""Deterministic critical-rule gate after list screening."""

from __future__ import annotations

import re
from typing import Any

from api.compliance.clarifications import has_open_requests
from api.compliance.models import PLDClarificationRequest
from api.compliance.risk.catalog import (
    INVITEE_SUMMARY,
    RISK_GATE_VERSION,
    classify_hit,
    max_semaphore,
)
from api.compliance.risk.schemas import RiskGateResult

_ORANGE_FINDINGS = frozenset(
    {"rfc_mismatch", "curp_mismatch", "controller_missing", "legal_name_mismatch"}
)
_YELLOW_FINDINGS = frozenset(
    {
        "id_expired_or_unreadable",
        "address_proof_stale",
        "acta_ownership_stale",
        "acta_extraction_thin",
    }
)


def _norm_name(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _payload_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _findings(expedient) -> list[dict]:
    prequal = _payload_dict(getattr(expedient, "prequalification_payload", None))
    raw = prequal.get("findings") or []
    return [item for item in raw if isinstance(item, dict)]


def _finding_codes(findings: list[dict]) -> set[str]:
    return {str(item.get("code") or "") for item in findings}


def _acta_thin(entity, expedient) -> bool:
    if getattr(entity, "person_type", "") != "persona_moral":
        return False
    docs = getattr(expedient, "documents", None)
    if docs is None:
        return False
    queryset = docs.all() if hasattr(docs, "all") else docs
    for doc in queryset:
        if getattr(doc, "document_kind", "") != "acta_constitutiva":
            continue
        payload = _payload_dict(getattr(doc, "extracted_payload", None))
        legal = str(payload.get("legal_name") or "").strip()
        shareholders = payload.get("shareholders") or []
        useful = isinstance(shareholders, list) and any(
            isinstance(row, dict) and str(row.get("name") or "").strip()
            for row in shareholders
        )
        return not legal and not useful
    return False


def _controllers_missing(entity) -> bool:
    if getattr(entity, "person_type", "") != "persona_moral":
        return False
    meta = _payload_dict(getattr(entity, "metadata", None))
    if meta.get("is_own_controller") is True:
        return False
    names: list[str] = []
    raw = meta.get("controllers")
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and str(item.get("name") or "").strip():
                names.append(str(item.get("name")).strip())
    single = meta.get("controller")
    if not names and isinstance(single, dict) and str(single.get("name") or "").strip():
        names.append(str(single.get("name")).strip())
    return len(names) == 0


def _open_screening(expedient) -> bool:
    try:
        return has_open_requests(expedient, PLDClarificationRequest.Stage.SCREENING)
    except Exception:
        return False


def _diligence_and_action(semaphore: str) -> tuple[int, str]:
    if semaphore == "red":
        return 3, "escalamiento"
    if semaphore == "orange":
        return 2, "edd"
    if semaphore == "yellow":
        return 2, "alta_condicionada"
    return 1, "alta"


def evaluate_risk_gate(entity, expedient) -> RiskGateResult:
    semaphore = "green"
    reasons: list[str] = []
    screening = _payload_dict(getattr(expedient, "screening_payload", None))
    verdict = str(screening.get("verdict") or "")
    hits = [item for item in (screening.get("hits") or []) if isinstance(item, dict)]
    codes = _finding_codes(_findings(expedient))

    screening_class = "none"
    fiscal_kind = ""
    for hit in hits:
        klass, fiscal = classify_hit(hit)
        strength = str(hit.get("strength") or "weak")
        if fiscal == "69b_desvirtuado":
            screening_class = "discarded" if screening_class == "none" else screening_class
            continue
        if klass == "confirmed":
            screening_class = "confirmed"
        elif screening_class == "none":
            screening_class = "possible"
        if fiscal and fiscal_kind != "69b_definitivo":
            fiscal_kind = fiscal
        if fiscal == "69b_presunto" and strength == "exact":
            semaphore = max_semaphore(semaphore, "orange")
            reasons.append("sat_69b_presunto")
        elif fiscal == "69b_definitivo" and strength == "exact":
            semaphore = max_semaphore(semaphore, "red")
            reasons.append("sat_69b_definitivo")
        elif fiscal == "onu" and strength == "exact":
            semaphore = max_semaphore(semaphore, "red")
            reasons.append("onu_exact")
        elif fiscal in {"art_69", "69b", "69b_bis"} and strength == "exact":
            semaphore = max_semaphore(semaphore, "orange")
            reasons.append("sat_69_exact")
        elif strength in {"weak", "strong"}:
            semaphore = max_semaphore(semaphore, "orange")
            reasons.append("possible_list_match")

    if verdict == "escalate" and any(
        str(hit.get("strength") or "") == "exact" for hit in hits
    ):
        semaphore = max_semaphore(semaphore, "red")
        reasons.append("screening_escalate_exact")
    elif verdict in {"human_review", "needs_invitee_input"}:
        semaphore = max_semaphore(semaphore, "orange")
        reasons.append("screening_unresolved")
        if screening_class == "none":
            screening_class = "possible"

    for code in sorted(codes & _ORANGE_FINDINGS):
        semaphore = max_semaphore(semaphore, "orange")
        reasons.append(code)
    for code in sorted(codes & _YELLOW_FINDINGS):
        semaphore = max_semaphore(semaphore, "yellow")
        reasons.append(code)

    if _controllers_missing(entity) and "controller_missing" not in reasons:
        semaphore = max_semaphore(semaphore, "orange")
        reasons.append("controller_missing")

    if _acta_thin(entity, expedient):
        semaphore = max_semaphore(semaphore, "yellow")
        reasons.append("acta_extraction_thin")

    open_screening = _open_screening(expedient)
    if open_screening:
        reasons.append("screening_clarification_open")

    unique_reasons = []
    for item in reasons:
        if item not in unique_reasons:
            unique_reasons.append(item)
    unique_reasons = unique_reasons[:5]

    if open_screening and semaphore == "green":
        semaphore = "yellow"

    diligence, action = _diligence_and_action(semaphore)
    if open_screening:
        action = "requerimiento"
        diligence = max(diligence, 2)

    ready = (
        semaphore == "green"
        and verdict == "clear"
        and not open_screening
    )
    return RiskGateResult(
        ruleset_version=RISK_GATE_VERSION,
        semaphore=semaphore,
        diligence_level=diligence,  # type: ignore[arg-type]
        recommended_action=action,  # type: ignore[arg-type]
        reasons=unique_reasons,
        screening_class=screening_class,  # type: ignore[arg-type]
        fiscal_list_kind=fiscal_kind,
        ready_for_signature=ready,
        invitee_summary=INVITEE_SUMMARY.get(semaphore, INVITEE_SUMMARY["green"]),
    )
