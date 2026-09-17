from __future__ import annotations

import logging

from celery import shared_task

from api.org_lists.models import OrganizationList
from api.org_lists.parse import TabularParseError, parse_tabular_upload
from api.org_lists.persist import mark_list_import_failed, replace_list_records

logger = logging.getLogger(__name__)


@shared_task
def process_organization_list_import(list_id: str) -> dict:
    try:
        org_list = OrganizationList.objects.select_related("organization").get(
            id=list_id
        )
    except OrganizationList.DoesNotExist:
        logger.warning("OrganizationList %s not found for import", list_id)
        return {"status": "error", "error": "not_found"}

    org_list.import_status = OrganizationList.ImportStatus.PROCESSING
    org_list.import_error = ""
    org_list.save(update_fields=["import_status", "import_error", "updated_at"])

    try:
        if not org_list.file:
            raise TabularParseError("List has no file attached.")
        org_list.file.open("rb")
        try:
            raw = org_list.file.read()
        finally:
            org_list.file.close()

        parsed = parse_tabular_upload(
            raw,
            filename=org_list.original_filename,
            content_type=org_list.content_type,
        )
        count = replace_list_records(org_list, parsed=parsed)
        return {"status": "succeeded", "list_id": str(org_list.id), "record_count": count}
    except TabularParseError as exc:
        logger.info("Organization list %s import failed: %s", list_id, exc)
        mark_list_import_failed(org_list, str(exc))
        return {"status": "failed", "error": str(exc)[:500]}
    except Exception as exc:
        logger.exception("Organization list %s import failed", list_id)
        mark_list_import_failed(org_list, str(exc))
        return {"status": "failed", "error": str(exc)[:500]}
