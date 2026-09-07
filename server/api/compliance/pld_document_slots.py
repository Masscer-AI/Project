"""Anexo 3 / 4 document checklist slots for an invitee expedient."""

from __future__ import annotations

from typing import Any


def _named_controllers(metadata: dict) -> list[dict[str, Any]]:
    raw = metadata.get("controllers")
    if isinstance(raw, list):
        named = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if name:
                named.append(item)
        if named:
            return named
    single = metadata.get("controller")
    if isinstance(single, dict):
        name = str(single.get("name") or "").strip()
        if name:
            return [single]
    return []


def _slot(
    slot_key: str,
    document_kind: str,
    *,
    required: bool,
    label_name: str | None = None,
) -> dict:
    payload = {
        "slot_key": slot_key,
        "document_kind": document_kind,
        "required": required,
    }
    if label_name:
        payload["label_name"] = label_name
    return payload


def required_slots_extraction_ready(entity) -> tuple[bool, str]:
    """True when every required checklist slot has a succeeded extraction."""
    from api.compliance.models import PLDExpedientDocument

    exp = entity.expedients.order_by("created_at").first()
    if not exp:
        return False, "expedient-not-found"
    uploaded = {doc.slot_key: doc for doc in exp.documents.all()}
    required = [slot for slot in document_slots_for_entity(entity) if slot["required"]]
    if not required:
        return False, "no-required-slots"
    for slot in required:
        doc = uploaded.get(slot["slot_key"])
        if not doc:
            return False, "missing-documents"
        if doc.extraction_status == PLDExpedientDocument.ExtractionStatus.FAILED:
            return False, "extraction-failed"
        if doc.extraction_status != PLDExpedientDocument.ExtractionStatus.SUCCEEDED:
            return False, "extraction-pending"
    return True, ""


def document_slots_for_entity(entity) -> list[dict]:
    """Return checklist slots from person type and saved identification metadata."""
    metadata = entity.metadata if isinstance(entity.metadata, dict) else {}
    if entity.person_type == "persona_moral":
        slots = [
            _slot("acta_constitutiva", "acta_constitutiva", required=True),
            _slot("constancia_fiscal", "constancia_fiscal", required=True),
            _slot("comprobante_domicilio", "comprobante_domicilio", required=True),
            _slot("id_representante", "id_representante", required=True),
            _slot("poder", "poder", required=False),
        ]
        for index, controller in enumerate(_named_controllers(metadata)):
            name = str(controller.get("name") or "").strip()
            slots.append(
                _slot(
                    f"id_controlador:{index}",
                    "id_controlador",
                    required=True,
                    label_name=name,
                )
            )
        return slots

    has_curp = bool(str(metadata.get("curp") or "").strip())
    has_rfc = bool(str(metadata.get("rfc") or "").strip())
    slots = [
        _slot("official_id", "official_id", required=True),
        _slot("curp", "curp", required=has_curp),
        _slot("constancia_fiscal", "constancia_fiscal", required=has_rfc),
        _slot("comprobante_domicilio", "comprobante_domicilio", required=True),
        _slot("poder", "poder", required=False),
    ]
    if metadata.get("is_own_controller") is False:
        for index, controller in enumerate(_named_controllers(metadata)):
            name = str(controller.get("name") or "").strip()
            slots.append(
                _slot(
                    f"id_controlador:{index}",
                    "id_controlador",
                    required=True,
                    label_name=name,
                )
            )
    return slots
