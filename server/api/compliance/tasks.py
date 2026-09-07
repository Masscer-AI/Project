"""Celery tasks for PLD expedient document extraction."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


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
        doc.save(
            update_fields=[
                "extracted_payload",
                "extraction_status",
                "extracted_at",
                "extraction_error",
                "updated_at",
            ]
        )
    except Exception:
        logger.exception("PLD extraction failed for %s", document_id)
        doc.extraction_status = PLDExpedientDocument.ExtractionStatus.FAILED
        doc.extraction_error = "extraction-failed"
        doc.save(
            update_fields=[
                "extraction_status",
                "extraction_error",
                "updated_at",
            ]
        )
        return

    from api.compliance.models import PLDExpedient
    from api.compliance.pld_document_slots import required_slots_extraction_ready

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
    except Exception:
        logger.exception("PLD prequalification failed for %s", expedient_id)
        exp.prequalification_status = PLDExpedient.PrequalificationStatus.FAILED
        exp.save(update_fields=["prequalification_status", "updated_at"])
