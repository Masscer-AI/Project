"""Celery tasks for PLD expedient document extraction."""

from __future__ import annotations

import logging

from celery import shared_task

from api.compliance.document_extraction.errors import public_extraction_error

logger = logging.getLogger(__name__)


def _save_extraction_fields(doc, fields: list[str], document_id: str) -> bool:
    from django.db import DatabaseError

    from api.compliance.models import PLDExpedientDocument

    if not PLDExpedientDocument.objects.filter(pk=document_id).exists():
        logger.warning(
            "PLD document %s was deleted during extraction; skipping save",
            document_id,
        )
        return False
    try:
        doc.save(update_fields=fields)
        return True
    except DatabaseError:
        if not PLDExpedientDocument.objects.filter(pk=document_id).exists():
            logger.warning(
                "PLD document %s was deleted during extraction; skipping save",
                document_id,
            )
            return False
        raise


@shared_task
def extract_pld_expedient_document(document_id: str):
    from django.utils import timezone

    from api.compliance.document_extraction import extract_document
    from api.compliance.models import PLDExpedientDocument

    try:
        doc = PLDExpedientDocument.objects.select_related(
            "expedient",
            "expedient__organization",
            "expedient__entity",
        ).get(pk=document_id)
    except (PLDExpedientDocument.DoesNotExist, ValueError):
        logger.warning("PLD document %s not found for extraction", document_id)
        return

    try:
        parsed = extract_document(doc)
        payload = parsed.model_dump(mode="json")
        from api.compliance.document_extraction.meta import extraction_meta

        payload["_meta"] = extraction_meta(doc, payload)
        doc.extracted_payload = payload
        doc.extraction_status = PLDExpedientDocument.ExtractionStatus.SUCCEEDED
        doc.extracted_at = timezone.now()
        doc.extraction_error = ""
        if not _save_extraction_fields(
            doc,
            [
                "extracted_payload",
                "extraction_status",
                "extracted_at",
                "extraction_error",
                "updated_at",
            ],
            document_id,
        ):
            return
    except Exception as exc:
        if not PLDExpedientDocument.objects.filter(pk=document_id).exists():
            logger.warning(
                "PLD document %s was deleted during extraction; skipping failure save",
                document_id,
            )
            return
        logger.exception("PLD extraction failed for %s", document_id)
        doc.extraction_status = PLDExpedientDocument.ExtractionStatus.FAILED
        doc.extraction_error = public_extraction_error(exc)
        _save_extraction_fields(
            doc,
            [
                "extraction_status",
                "extraction_error",
                "updated_at",
            ],
            document_id,
        )
        return

    from api.compliance.clarifications import (
        mark_answered,
        maybe_resume_stage,
        parse_clarification_slot,
    )
    from api.compliance.models import PLDClarificationRequest, PLDExpedient
    from api.compliance.pld_document_slots import required_slots_extraction_ready

    request_id = parse_clarification_slot(doc.slot_key)
    if request_id:
        req = PLDClarificationRequest.objects.filter(
            pk=request_id, expedient=doc.expedient
        ).first()
        if req and req.status == PLDClarificationRequest.Status.OPEN:
            mark_answered(req)
        maybe_resume_stage(doc.expedient)
        return

    entity = doc.expedient.entity
    ready, _ = required_slots_extraction_ready(entity)
    if ready:
        exp = doc.expedient
        exp.prequalification_status = PLDExpedient.PrequalificationStatus.PENDING
        exp.save(update_fields=["prequalification_status", "updated_at"])
        prequalify_pld_expedient.delay(str(exp.id))


@shared_task
def prequalify_pld_expedient(expedient_id: str):
    from django.utils import timezone

    from api.compliance.models import PLDExpedient
    from api.compliance.prequalification import run_prequalification

    try:
        exp = PLDExpedient.objects.select_related(
            "entity", "entity__organization", "organization"
        ).prefetch_related("documents", "entity__expedients", "entity__expedients__documents").get(
            pk=expedient_id
        )
    except (PLDExpedient.DoesNotExist, ValueError):
        logger.warning("PLD expedient %s not found for prequalification", expedient_id)
        return

    entity = exp.entity
    exp.prequalification_status = PLDExpedient.PrequalificationStatus.PENDING
    exp.save(update_fields=["prequalification_status", "updated_at"])
    try:
        parsed = run_prequalification(entity)
        exp.prequalification_payload = parsed.model_dump(mode="json")
        exp.prequalification_status = PLDExpedient.PrequalificationStatus.SUCCEEDED
        exp.prequalified_at = timezone.now()
        exp.save(
            update_fields=[
                "prequalification_payload",
                "prequalification_status",
                "prequalified_at",
                "updated_at",
            ]
        )
        from api.compliance.clarifications import replace_open_requests
        from api.compliance.models import PLDClarificationRequest

        replace_open_requests(
            exp,
            PLDClarificationRequest.Stage.IDENTIFICATION,
            list(parsed.invitee_requests or []),
        )
    except Exception:
        logger.exception("PLD prequalification failed for %s", expedient_id)
        exp.prequalification_status = PLDExpedient.PrequalificationStatus.FAILED
        exp.save(update_fields=["prequalification_status", "updated_at"])


@shared_task
def screen_pld_expedient(expedient_id: str):
    from django.utils import timezone

    from api.compliance.clarifications import replace_open_requests
    from api.compliance.models import PLDClarificationRequest, PLDExpedient
    from api.compliance.screening import run_screening

    try:
        exp = PLDExpedient.objects.select_related(
            "entity", "entity__organization", "organization"
        ).prefetch_related(
            "documents",
            "clarification_requests",
            "entity__expedients",
            "entity__expedients__documents",
        ).get(pk=expedient_id)
    except (PLDExpedient.DoesNotExist, ValueError):
        logger.warning("PLD expedient %s not found for screening", expedient_id)
        return

    entity = exp.entity
    exp.screening_status = PLDExpedient.PrequalificationStatus.PENDING
    exp.save(update_fields=["screening_status", "updated_at"])
    try:
        parsed = run_screening(entity)
        exp.screening_payload = parsed.model_dump(mode="json")
        exp.screening_status = PLDExpedient.PrequalificationStatus.SUCCEEDED
        exp.screened_at = timezone.now()
        exp.save(
            update_fields=[
                "screening_payload",
                "screening_status",
                "screened_at",
                "updated_at",
            ]
        )
        replace_open_requests(
            exp,
            PLDClarificationRequest.Stage.SCREENING,
            list(parsed.invitee_requests or []),
        )
        from api.compliance.risk import evaluate_risk_gate

        risk = evaluate_risk_gate(entity, exp)
        exp.risk_payload = risk.model_dump(mode="json")
        exp.risk_status = PLDExpedient.PrequalificationStatus.SUCCEEDED
        exp.risked_at = timezone.now()
        exp.save(
            update_fields=[
                "risk_payload",
                "risk_status",
                "risked_at",
                "updated_at",
            ]
        )
        from api.compliance.packet import maybe_dispatch_identification_packet

        maybe_dispatch_identification_packet(exp)
    except Exception:
        logger.exception("PLD screening failed for %s", expedient_id)
        exp.screening_status = PLDExpedient.PrequalificationStatus.FAILED
        exp.save(update_fields=["screening_status", "updated_at"])


@shared_task
def ingest_watchlists(force: bool = False):
    from api.compliance.watchlists.ingest import ingest_all_watchlists

    return ingest_all_watchlists(force=force)
