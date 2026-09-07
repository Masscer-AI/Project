"""Assemble the compact packet the pre-qualification agent reads."""

from __future__ import annotations

import json

from api.compliance.pld_document_slots import document_slots_for_entity
from api.compliance.prequalification.deterministic import deterministic_findings
from api.compliance.prequalification.rules import IDENTIFICATION_RULES
from api.compliance.prequalification.sources import RULESET_VERSION


def _compact_payload(payload: dict) -> dict:
    skip = {"provenances"}
    compact = {key: value for key, value in payload.items() if key not in skip}
    provenances = payload.get("provenances")
    if isinstance(provenances, list):
        compact["provenances"] = [
            {
                "campo_id": item.get("campo_id"),
                "valor_extraido": item.get("valor_extraido"),
                "pagina_origen": item.get("pagina_origen"),
                "estado_validacion": item.get("estado_validacion"),
            }
            for item in provenances
            if isinstance(item, dict)
        ][:40]
    return compact


def build_prequalification_packet(entity) -> str:
    exp = entity.expedients.order_by("created_at").first()
    docs = []
    if exp:
        for doc in exp.documents.all():
            payload = doc.extracted_payload if isinstance(doc.extracted_payload, dict) else {}
            docs.append(
                {
                    "slot_key": doc.slot_key,
                    "document_kind": doc.document_kind,
                    "original_filename": doc.original_filename,
                    "extraction_status": doc.extraction_status,
                    "extracted": _compact_payload(payload),
                }
            )
    packet = {
        "ruleset_version": RULESET_VERSION,
        "person_type": entity.person_type,
        "relationship": entity.relationship,
        "declared": entity.metadata if isinstance(entity.metadata, dict) else {},
        "slots": document_slots_for_entity(entity),
        "documents": docs,
        "deterministic_findings": [
            item.model_dump(mode="json") for item in deterministic_findings(entity)
        ],
        "rules": IDENTIFICATION_RULES,
    }
    return json.dumps(packet, ensure_ascii=False, default=str)
