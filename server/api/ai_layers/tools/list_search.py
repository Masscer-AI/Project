"""
Tool: list_search

Search rows in organization uploaded lists (Knowledge Base → Lists).
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from api.org_lists.search import (
    DEFAULT_SEARCH_LIMIT,
    MAX_SEARCH_LIMIT,
    search_organization_list_records,
)

logger = logging.getLogger(__name__)


class ListSearchParams(BaseModel):
    terms: list[str] = Field(
        min_length=1,
        description="One or more search terms. Every term must match (AND).",
    )
    list_id: str | None = Field(
        default=None,
        description="Optional list UUID from list_organization_lists. Omit to search all lists.",
    )
    limit: int = Field(
        default=DEFAULT_SEARCH_LIMIT,
        ge=1,
        le=MAX_SEARCH_LIMIT,
        description="Maximum number of matching rows to return.",
    )


class ListSearchHit(BaseModel):
    list_id: str
    list_name: str
    position: int
    data: dict[str, str] = Field(default_factory=dict)


class ListSearchResult(BaseModel):
    terms: list[str] = Field(default_factory=list)
    hits: list[ListSearchHit] = Field(default_factory=list)
    truncated: bool = False
    message: str = ""


def list_search_impl(
    *,
    organization_id: int,
    terms: list[str],
    list_id: str | None = None,
    limit: int = DEFAULT_SEARCH_LIMIT,
) -> ListSearchResult:
    cleaned = [part.strip() for part in terms if part and str(part).strip()]
    if not cleaned:
        return ListSearchResult(terms=[], message="No search terms.")

    rows, tokens, truncated = search_organization_list_records(
        organization_id=organization_id,
        terms=cleaned,
        list_id=list_id,
        limit=limit,
    )

    hits: list[ListSearchHit] = []
    for row in rows:
        data = row.data if isinstance(row.data, dict) else {}
        hits.append(
            ListSearchHit(
                list_id=str(row.organization_list_id),
                list_name=row.organization_list.name,
                position=row.position,
                data={str(k): str(v) for k, v in data.items()},
            )
        )

    return ListSearchResult(
        terms=tokens or cleaned,
        hits=hits,
        truncated=truncated,
        message=f"{len(hits)} hit(s).",
    )


def get_tool(
    organization_id: int | None = None,
    **kwargs,
) -> dict:
    if organization_id is None:
        raise ValueError("list_search requires organization_id in tool context")

    org_id = int(organization_id)

    def list_search(
        terms: list[str],
        list_id: str | None = None,
        limit: int = DEFAULT_SEARCH_LIMIT,
    ) -> ListSearchResult:
        return list_search_impl(
            organization_id=org_id,
            terms=terms,
            list_id=list_id,
            limit=limit,
        )

    return {
        "name": "list_search",
        "description": (
            "Search rows in organization uploaded lists (CSV/Excel catalogs). "
            "Pass one or more terms; all must appear (AND). "
            "Use list_organization_lists first to discover list ids and columns; "
            "then pass list_id when searching a specific list. "
            "Omit list_id to search across all ready lists. "
            "Not for compliance watchlists, RAG memory, or knowledge-base documents."
        ),
        "parameters": ListSearchParams,
        "function": list_search,
    }
