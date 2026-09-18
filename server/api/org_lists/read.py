from __future__ import annotations

import uuid

from api.org_lists.models import OrganizationList, OrganizationListRecord

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def read_organization_list_records(
    *,
    organization_id,
    list_id: str | uuid.UUID,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> tuple[OrganizationList | None, list[OrganizationListRecord], int, int, int]:
    """
    Paginated rows for one succeeded org list.

    Returns (org_list_or_none, records, page, page_size, total).
    org_list is None when the list is missing or not ready.
    """
    try:
        org_list = OrganizationList.objects.get(
            id=list_id,
            organization_id=organization_id,
            import_status=OrganizationList.ImportStatus.SUCCEEDED,
        )
    except OrganizationList.DoesNotExist:
        return None, [], 1, DEFAULT_PAGE_SIZE, 0

    cap = max(1, min(int(page_size or DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE))
    page_num = max(1, int(page or 1))
    qs = OrganizationListRecord.objects.filter(organization_list=org_list).order_by(
        "position"
    )
    total = qs.count()
    start = (page_num - 1) * cap
    records = list(qs[start : start + cap])
    return org_list, records, page_num, cap, total
