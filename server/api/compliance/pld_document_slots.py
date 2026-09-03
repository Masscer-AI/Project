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
