from __future__ import annotations

from django.db.models import QuerySet

from api.compliance.models import WatchlistListSlug, WatchlistRecord
from api.compliance.watchlists.normalize import fold_text


def search_terms(query: str | list[str] | None) -> list[str]:
    if query is None:
        return []
    if isinstance(query, str):
        parts = query.split()
    else:
        parts = list(query)
    terms: list[str] = []
    seen: set[str] = set()
    for part in parts:
        folded = fold_text(part)
        if not folded or folded in seen:
            continue
        seen.add(folded)
        terms.append(folded)
    return terms


def search_watchlist_records(
    *terms: str,
    query: str | list[str] | None = None,
    list_slug: str = WatchlistListSlug.ONU_CSNU,
    record_type: str | None = None,
    current_only: bool = True,
) -> QuerySet[WatchlistRecord]:
    """AND-search: every term must appear in the folded search_document."""
    qs = WatchlistRecord.objects.all()
    if current_only:
        qs = qs.filter(snapshot__is_current=True)
    if list_slug:
        qs = qs.filter(snapshot__list_slug=list_slug)
    if record_type:
        qs = qs.filter(record_type=record_type)

    combined = list(terms)
    if query is not None:
        if isinstance(query, str):
            combined.extend(query.split())
        else:
            combined.extend(query)
    tokens = search_terms(combined)

    for token in tokens:
        qs = qs.filter(search_document__contains=token)
    return qs.select_related("snapshot")
