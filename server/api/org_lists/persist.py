from __future__ import annotations

import logging

from django.db import transaction

from api.compliance.watchlists.normalize import build_search_document
from api.org_lists.models import OrganizationList, OrganizationListRecord
from api.org_lists.parse import build_config_from_table
from api.org_lists.schemas import validate_list_config_for_storage

logger = logging.getLogger(__name__)


def _search_document_for_row(data: dict[str, str]) -> str:
    return build_search_document(list(data.values()))


@transaction.atomic
def replace_list_records(
    org_list: OrganizationList,
    *,
    parsed: dict,
    config: dict | None = None,
) -> int:
    headers = parsed["headers"]
    rows = parsed["rows"]
    sheet_name = parsed.get("sheet_name")
    if config is None:
        config = build_config_from_table(headers, rows)
    else:
        config = validate_list_config_for_storage(config)
    if sheet_name:
        config = {**config, "sheet_name": sheet_name}

    OrganizationListRecord.objects.filter(organization_list=org_list).delete()

    batch: list[OrganizationListRecord] = []
    count = 0
    for idx, row in enumerate(rows, start=1):
        batch.append(
            OrganizationListRecord(
                organization_list=org_list,
                position=idx,
                data=row,
                search_document=_search_document_for_row(row),
            )
        )
        if len(batch) >= 500:
            OrganizationListRecord.objects.bulk_create(batch, batch_size=500)
            count += len(batch)
            batch = []
    if batch:
        OrganizationListRecord.objects.bulk_create(batch, batch_size=500)
        count += len(batch)

    org_list.config = config
    org_list.record_count = count
    org_list.import_status = OrganizationList.ImportStatus.SUCCEEDED
    org_list.import_error = ""
    org_list.save(
        update_fields=[
            "config",
            "record_count",
            "import_status",
            "import_error",
            "updated_at",
        ]
    )
    logger.info(
        "Organization list %s import succeeded (%s records)",
        org_list.id,
        count,
    )
    return count


def mark_list_import_failed(org_list: OrganizationList, error: str) -> None:
    org_list.import_status = OrganizationList.ImportStatus.FAILED
    org_list.import_error = (error or "Import failed.")[:4000]
    org_list.save(update_fields=["import_status", "import_error", "updated_at"])
