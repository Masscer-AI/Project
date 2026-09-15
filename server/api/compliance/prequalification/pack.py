"""Assemble the compact packet the pre-qualification agent reads."""

from __future__ import annotations

import json

from api.compliance.pld_document_slots import document_slots_for_entity
from api.compliance.clarifications import answers_packet
from api.compliance.prequalification.rules import IDENTIFICATION_RULES
from api.compliance.prequalification.sources import RULESET_VERSION


def _compact_payload(payload: dict) -> dict:
    skip = {"provenances", "ownership_may_be_stale"}
    return {key: value for key, value in payload.items() if key not in skip}


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
        "rules": IDENTIFICATION_RULES,
        "prior_invitee_answers": [
            {
                **row,
                "document_extraction": (
                    _compact_payload(row["document_extraction"])
                    if isinstance(row.get("document_extraction"), dict)
                    else row.get("document_extraction")
                ),
            }
            for row in (answers_packet(exp) if exp else [])
        ],
    }
    return json.dumps(packet, ensure_ascii=False, default=str)
