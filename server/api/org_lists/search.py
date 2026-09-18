from __future__ import annotations

import uuid

from api.compliance.watchlists.search import search_terms
from api.org_lists.models import OrganizationList, OrganizationListRecord

DEFAULT_SEARCH_LIMIT = 50
MAX_SEARCH_LIMIT = 200


def search_organization_list_records(
    *,
    organization_id,
    terms: list[str] | str | None = None,
    list_id: str | uuid.UUID | None = None,
    limit: int = DEFAULT_SEARCH_LIMIT,
) -> tuple[list[OrganizationListRecord], list[str], bool]:
    """
    AND-search: every folded term must appear in search_document.

    Returns (records, cleaned_tokens, truncated).
    """
    qs = OrganizationListRecord.objects.filter(
        organization_list__organization_id=organization_id,
        organization_list__import_status=OrganizationList.ImportStatus.SUCCEEDED,
    ).select_related("organization_list")

    if list_id:
        qs = qs.filter(organization_list_id=list_id)

    tokens = search_terms(terms)
    for token in tokens:
        qs = qs.filter(search_document__contains=token)

    cap = max(1, min(int(limit or DEFAULT_SEARCH_LIMIT), MAX_SEARCH_LIMIT))
    rows = list(
        qs.order_by("organization_list__name", "position")[: cap + 1]
    )
    truncated = len(rows) > cap
    if truncated:
        rows = rows[:cap]
    return rows, tokens, truncated
