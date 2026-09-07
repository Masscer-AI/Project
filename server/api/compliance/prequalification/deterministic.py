"""Code checks against IDENTIFICATION_RULES (no LLM)."""

from __future__ import annotations

import re
from typing import Any

from api.compliance.document_extraction.spec_fields import missing_spec_fields
from api.compliance.pld_document_slots import (
    document_slots_for_entity,
    required_slots_extraction_ready,
)
from api.compliance.pld_metadata import identification_is_complete
from api.compliance.prequalification.schemas import PrequalFinding
from api.compliance.prequalification.sources import RULESET_VERSION


def _norm_key(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _payload(doc) -> dict:
    raw = getattr(doc, "extracted_payload", None)
    return raw if isinstance(raw, dict) else {}


def _docs_by_kind(entity) -> dict[str, list]:
    exp = entity.expedients.order_by("created_at").first()
    grouped: dict[str, list] = {}
    if not exp:
        return grouped
    for doc in exp.documents.all():
        grouped.setdefault(doc.document_kind, []).append(doc)
    return grouped


def _first_payload(grouped: dict[str, list], kind: str) -> dict:
    docs = grouped.get(kind) or []
    return _payload(docs[0]) if docs else {}


def deterministic_findings(entity) -> list[PrequalFinding]:
    findings: list[PrequalFinding] = []
    metadata = entity.metadata if isinstance(entity.metadata, dict) else {}
    if not identification_is_complete(entity.person_type, metadata):
        findings.append(
            PrequalFinding(
                code="identification_incomplete",
                severity="blocker",
                target="metadata",
                summary="Faltan datos obligatorios de identificacion declarados por la contraparte.",
                source_ids=["rcg"],
            )
        )
    ready, reason = required_slots_extraction_ready(entity)
    if not ready:
        findings.append(
            PrequalFinding(
                code=reason or "documents_not_ready",
                severity="blocker",
                target="documents",
                summary="El expediente documental obligatorio no esta extraido por completo.",
                evidence=reason,
                source_ids=["rcg"],
            )
        )

    grouped = _docs_by_kind(entity)
    for slot in document_slots_for_entity(entity):
        if not slot.get("required"):
            continue
        kind = slot["document_kind"]
        docs = grouped.get(kind) or []
        slot_docs = [d for d in docs if d.slot_key == slot["slot_key"]] or docs
        for doc in slot_docs:
            payload = _payload(doc)
            missing = missing_spec_fields(kind, payload)
            if missing:
                findings.append(
                    PrequalFinding(
                        code="extraction_fields_missing",
                        severity="warning",
                        target=doc.slot_key,
                        summary="La extraccion no cubrio todos los campos del tipo documental.",
                        evidence=", ".join(missing[:12]),
                        source_ids=["rcg"],
                    )
                )

    comprobantes = grouped.get("comprobante_domicilio") or []
    for doc in comprobantes:
        payload = _payload(doc)
        if payload.get("older_than_three_months") is True:
            findings.append(
                PrequalFinding(
                    code="address_proof_stale",
                    severity="blocker",
                    target=doc.slot_key,
                    summary="El comprobante de domicilio tiene antiguedad mayor a tres meses.",
                    evidence=str(payload.get("issue_or_period_date") or ""),
                    source_ids=["rcg"],
                )
            )

    for kind in ("official_id", "id_representante", "id_controlador"):
        for doc in grouped.get(kind) or []:
            payload = _payload(doc)
            if payload.get("expired_or_unreadable") is True:
                findings.append(
                    PrequalFinding(
                        code="id_expired_or_unreadable",
                        severity="blocker",
                        target=doc.slot_key,
                        summary="La identificacion oficial parece vencida o ilegible.",
                        source_ids=["rcg"],
                    )
                )

    declared_rfc = _norm_key(metadata.get("rfc"))
    csf = _first_payload(grouped, "constancia_fiscal")
    extracted_rfc = _norm_key(csf.get("rfc"))
    if declared_rfc and extracted_rfc and declared_rfc != extracted_rfc:
        findings.append(
            PrequalFinding(
                code="rfc_mismatch",
                severity="blocker",
                target="constancia_fiscal",
                summary="El RFC declarado no coincide con la constancia de situacion fiscal.",
                evidence=f"declared={declared_rfc} csf={extracted_rfc}",
                source_ids=["rcg"],
            )
        )

    declared_curp = _norm_key(metadata.get("curp"))
    curp_doc = _first_payload(grouped, "curp")
    extracted_curp = _norm_key(curp_doc.get("curp"))
    if declared_curp and extracted_curp and declared_curp != extracted_curp:
        findings.append(
            PrequalFinding(
                code="curp_mismatch",
                severity="blocker",
                target="curp",
                summary="La CURP declarada no coincide con la constancia CURP.",
                evidence=f"declared={declared_curp} doc={extracted_curp}",
                source_ids=["rcg"],
            )
        )

    if entity.person_type == "persona_moral":
        acta = _first_payload(grouped, "acta_constitutiva")
        if acta.get("ownership_may_be_stale") is True:
            findings.append(
                PrequalFinding(
                    code="acta_ownership_stale",
                    severity="warning",
                    target="acta_constitutiva",
                    summary="La participacion del acta es al momento de constitucion y puede estar desactualizada frente al beneficiario controlador declarado.",
                    source_ids=["rcg"],
                )
            )

    return findings


def verdict_from_findings(findings: list[PrequalFinding]) -> str:
    if any(item.severity == "blocker" for item in findings):
        return "blocked"
    if any(item.severity == "warning" for item in findings):
        return "needs_review"
    return "ready_for_list_screening"


def controller_names(entity) -> list[str]:
    metadata = entity.metadata if isinstance(entity.metadata, dict) else {}
    names: list[str] = []
    raw = metadata.get("controllers")
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                name = str(item.get("name") or "").strip()
                if name:
                    names.append(name)
    single = metadata.get("controller")
    if not names and isinstance(single, dict):
        name = str(single.get("name") or "").strip()
        if name:
            names.append(name)
    if metadata.get("is_own_controller") is True and not names:
        name = str(metadata.get("name") or "").strip()
        if name:
            names.append(name)
    return names


def empty_running_payload() -> dict:
    return {
        "ruleset_version": RULESET_VERSION,
        "verdict": "blocked",
        "summary": "",
        "findings": [],
        "controllers": [],
        "human_notes": None,
        "status": "pending",
    }
