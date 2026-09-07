from __future__ import annotations

import re

from pydantic import BaseModel, Field

from api.compliance.models import WatchlistListSlug
from api.compliance.watchlists.search import search_watchlist_records

RFC_RE = re.compile(r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$", re.I)
NAME_SEARCH_LISTS = (
    WatchlistListSlug.ONU_CSNU,
    WatchlistListSlug.SAT_69B,
    WatchlistListSlug.SAT_69B_BIS,
)
RFC_SEARCH_LISTS = (
    WatchlistListSlug.SAT_69B,
    WatchlistListSlug.SAT_69B_BIS,
    WatchlistListSlug.SAT_69_FIRMES,
    WatchlistListSlug.SAT_69_NO_LOCALIZADOS,
    WatchlistListSlug.SAT_69_EXIGIBLES,
    WatchlistListSlug.SAT_69_SENTENCIAS,
    WatchlistListSlug.SAT_69_CSD,
)


class SearchWatchlistsParams(BaseModel):
    terms: list[str] = Field(
        min_length=1,
        description="One or more search terms. Every term must match (AND).",
    )
    list_slug: str | None = Field(
        default=None,
        description="Optional list id, e.g. onu_csnu or sat_69b. Omit to search the default set.",
    )
    record_type: str | None = Field(
        default=None,
        description="Optional: individual or entity.",
    )


class WatchlistHit(BaseModel):
    list_slug: str
    reference_number: str
    primary_name: str
    record_type: str
    listed_on: str = ""
    situation: str = ""


class SearchWatchlistsResult(BaseModel):
    terms: list[str]
    hits: list[WatchlistHit] = Field(default_factory=list)
    truncated: bool = False
    message: str = ""


def _situation(raw) -> str:
    if not isinstance(raw, dict):
        return ""
    for key in (
        "situacion del contribuyente",
        "supuesto",
        "supuesto de cancelacion csd",
    ):
        value = raw.get(key)
        if value:
            return str(value).strip()
    return ""


def _looks_like_rfc(terms: list[str]) -> bool:
    if len(terms) != 1:
        return False
    compact = re.sub(r"\s+", "", terms[0] or "")
    return bool(RFC_RE.match(compact))


def search_watchlists_impl(
    terms: list[str],
    *,
    list_slug: str | None = None,
    record_type: str | None = None,
    limit: int = 20,
) -> SearchWatchlistsResult:
    cleaned = [part.strip() for part in terms if part and str(part).strip()]
    if not cleaned:
        return SearchWatchlistsResult(terms=[], message="No search terms.")
    slugs: list[str]
    if list_slug:
        slugs = [list_slug]
    elif _looks_like_rfc(cleaned):
        slugs = list(RFC_SEARCH_LISTS)
    else:
        slugs = list(NAME_SEARCH_LISTS)

    hits: list[WatchlistHit] = []
    truncated = False
    per_list = max(3, limit // max(len(slugs), 1))
    for slug in slugs:
        qs = search_watchlist_records(
            query=cleaned,
            list_slug=slug,
            record_type=record_type,
        )[:per_list]
        for row in qs:
            hits.append(
                WatchlistHit(
                    list_slug=row.snapshot.list_slug,
                    reference_number=row.reference_number,
                    primary_name=row.primary_name,
                    record_type=row.record_type,
                    listed_on=row.listed_on or "",
                    situation=_situation(row.raw),
                )
            )
            if len(hits) >= limit:
                truncated = True
                break
        if truncated:
            break
    return SearchWatchlistsResult(
        terms=cleaned,
        hits=hits,
        truncated=truncated,
        message=f"{len(hits)} hit(s).",
    )


def make_search_watchlists_tool() -> dict:
    def search_watchlists(
        terms: list[str],
        list_slug: str | None = None,
        record_type: str | None = None,
    ) -> SearchWatchlistsResult:
        return search_watchlists_impl(
            terms, list_slug=list_slug, record_type=record_type
        )

    return {
        "name": "search_watchlists",
        "description": (
            "Search current official watchlists. Pass one or many terms; all terms "
            "must appear (AND). Use RFC alone for SAT lists. Use name tokens for ONU. "
            "Call more than once for alternate spellings (OR). Never tell the invitee "
            "the hit details."
        ),
        "parameters": SearchWatchlistsParams,
        "function": search_watchlists,
    }
