from __future__ import annotations

from typing import Literal

from django.utils import timezone
from pydantic import BaseModel, ConfigDict, Field

from api.compliance.models import (
    PLDClarificationRequest,
    PLDExpedient,
    PLDExpedientDocument,
    PLDExpedientStatus,
)

MAX_INVITEE_REQUESTS = 5

DETERMINISTIC_PROMPTS = {
    "rfc_mismatch": (
        "El RFC que declaraste no coincide con el de tu constancia fiscal. "
        "Escribe el RFC correcto o sube una constancia actualizada.",
        "either",
        "rfc",
    ),
    "curp_mismatch": (
        "La CURP que declaraste no coincide con el documento CURP. "
        "Escribe la CURP correcta o sube el documento actualizado.",
        "either",
        "curp",
    ),
}


class InviteeRequestSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    prompt: str = Field(max_length=400)
    answer_type: Literal["text", "document", "either"] = "text"
    target: str | None = None


def clarification_slot_key(request_id) -> str:
    return f"clarify:{request_id}"


def parse_clarification_slot(slot_key: str):
    prefix = "clarify:"
    if not slot_key.startswith(prefix):
        return None
    return slot_key[len(prefix) :]


def specs_from_findings(findings) -> list[InviteeRequestSpec]:
    specs: list[InviteeRequestSpec] = []
    seen: set[str] = set()
    for item in findings:
        code = getattr(item, "code", None) or (item.get("code") if isinstance(item, dict) else None)
        if not code or code in seen or code not in DETERMINISTIC_PROMPTS:
            continue
        seen.add(code)
        prompt, answer_type, target = DETERMINISTIC_PROMPTS[code]
        specs.append(
            InviteeRequestSpec(prompt=prompt, answer_type=answer_type, target=target)
        )
    return specs


def merge_request_specs(
    *groups: list[InviteeRequestSpec],
) -> list[InviteeRequestSpec]:
    merged: list[InviteeRequestSpec] = []
    seen: set[str] = set()
    for group in groups:
        for spec in group:
            prompt = (spec.prompt or "").strip()
            if not prompt:
                continue
            key = prompt.casefold()
            if key in seen:
                continue
            seen.add(key)
            merged.append(
                InviteeRequestSpec(
                    prompt=prompt[:400],
                    answer_type=spec.answer_type or "text",
                    target=(spec.target or "").strip()[:64] or None,
                )
            )
            if len(merged) >= MAX_INVITEE_REQUESTS:
                return merged
    return merged


def replace_open_requests(
    expedient: PLDExpedient,
    stage: str,
    specs: list[InviteeRequestSpec],
) -> list[PLDClarificationRequest]:
    PLDClarificationRequest.objects.filter(
        expedient=expedient,
        stage=stage,
        status=PLDClarificationRequest.Status.OPEN,
    ).update(
        status=PLDClarificationRequest.Status.CANCELLED,
        updated_at=timezone.now(),
    )
    created: list[PLDClarificationRequest] = []
    for spec in merge_request_specs(specs):
        created.append(
            PLDClarificationRequest.objects.create(
                expedient=expedient,
                stage=stage,
                prompt=spec.prompt,
                answer_type=spec.answer_type,
                target=spec.target or "",
            )
        )
    if created and expedient.status == PLDExpedientStatus.DOCUMENT_COLLECTION:
        expedient.status = PLDExpedientStatus.ACTION_REQUIRED
        expedient.save(update_fields=["status", "updated_at"])
    return created


def has_open_requests(expedient: PLDExpedient, stage: str | None = None) -> bool:
    qs = expedient.clarification_requests.filter(
        status=PLDClarificationRequest.Status.OPEN
    )
    if stage:
        qs = qs.filter(stage=stage)
    return qs.exists()


def serialize_request(item: PLDClarificationRequest, documents_by_slot: dict | None = None) -> dict:
    documents_by_slot = documents_by_slot or {}
    doc = documents_by_slot.get(item.slot_key)
    return {
        "id": str(item.id),
        "stage": item.stage,
        "prompt": item.prompt,
        "answer_type": item.answer_type,
        "target": item.target,
        "status": item.status,
        "text_answer": item.text_answer,
        "slot_key": item.slot_key,
        "document": doc,
        "answered_at": item.answered_at.isoformat() if item.answered_at else None,
    }


def answers_packet(expedient: PLDExpedient) -> list[dict]:
    rows = []
    docs = {doc.slot_key: doc for doc in expedient.documents.all()}
    for item in expedient.clarification_requests.exclude(
        status=PLDClarificationRequest.Status.CANCELLED
    ):
        doc = docs.get(item.slot_key)
        payload = doc.extracted_payload if doc and isinstance(doc.extracted_payload, dict) else {}
        rows.append(
            {
                "id": str(item.id),
                "stage": item.stage,
                "prompt": item.prompt,
                "target": item.target,
                "status": item.status,
                "text_answer": item.text_answer,
                "document_extraction": payload or None,
                "document_filename": getattr(doc, "original_filename", "") if doc else "",
            }
        )
    return rows


def apply_text_to_metadata(entity, request: PLDClarificationRequest, text: str) -> None:
    from api.compliance.pld_metadata import normalize_pld_entity_metadata

    value = text.strip()
    if not value or not request.target:
        return
    meta = dict(entity.metadata) if isinstance(entity.metadata, dict) else {}
    target = request.target
    if target == "rfc":
        meta["rfc"] = value.upper()
    elif target == "curp":
        meta["curp"] = value.upper()
    elif target in {"legal_name", "name"}:
        if entity.person_type == "persona_moral":
            meta["legal_name"] = value
        else:
            meta["name"] = value
    else:
        return
    entity.metadata = normalize_pld_entity_metadata(entity.person_type, meta)
    entity.save(update_fields=["metadata", "updated_at"])


def mark_answered(request: PLDClarificationRequest, *, text: str = "") -> None:
    request.status = PLDClarificationRequest.Status.ANSWERED
    if text:
        request.text_answer = text.strip()[:4000]
    request.answered_at = timezone.now()
    request.save(update_fields=["status", "text_answer", "answered_at", "updated_at"])


def maybe_resume_stage(expedient: PLDExpedient) -> None:
    from api.compliance.tasks import prequalify_pld_expedient, screen_pld_expedient

    pending_extract = expedient.documents.filter(
        slot_key__startswith="clarify:",
        extraction_status=PLDExpedientDocument.ExtractionStatus.PENDING,
    ).exists()
    if pending_extract:
        return

    if expedient.status in {
        PLDExpedientStatus.DOCUMENT_COLLECTION,
        PLDExpedientStatus.ACTION_REQUIRED,
    }:
        if has_open_requests(expedient, PLDClarificationRequest.Stage.IDENTIFICATION):
            return
        if expedient.status == PLDExpedientStatus.ACTION_REQUIRED:
            expedient.status = PLDExpedientStatus.DOCUMENT_COLLECTION
            expedient.save(update_fields=["status", "updated_at"])
        expedient.prequalification_status = PLDExpedient.PrequalificationStatus.PENDING
        expedient.save(update_fields=["prequalification_status", "updated_at"])
        prequalify_pld_expedient.delay(str(expedient.id))
        return

    if expedient.status == PLDExpedientStatus.CROSS_REFERENCE:
        if has_open_requests(expedient, PLDClarificationRequest.Stage.SCREENING):
            return
        expedient.screening_status = PLDExpedient.PrequalificationStatus.PENDING
        expedient.save(update_fields=["screening_status", "updated_at"])
        screen_pld_expedient.delay(str(expedient.id))
