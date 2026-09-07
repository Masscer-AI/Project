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
            "expedient", "expedient__organization"
        ).get(pk=document_id)
    except (PLDExpedientDocument.DoesNotExist, ValueError):
        logger.warning("PLD document %s not found for extraction", document_id)
        return

    try:
        parsed = extract_document(doc)
        doc.extracted_payload = parsed.model_dump(mode="json")
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
