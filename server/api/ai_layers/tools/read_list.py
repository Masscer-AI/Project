"""
Tool: read_list

Paginated read of rows in one organization uploaded list.
Shown as its own agent toggle (not bundled with list_search).
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from api.org_lists.read import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    read_organization_list_records,
)

logger = logging.getLogger(__name__)


class ReadListParams(BaseModel):
    list_id: str = Field(
        description="List UUID from list_organization_lists.",
    )
    page: int = Field(
        default=1,
        ge=1,
        description="1-based page number when the list has more rows than page_size.",
    )
    page_size: int = Field(
        default=DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description="Rows per page (default 50, max 200).",
    )


class ReadListRow(BaseModel):
    position: int
    data: dict[str, str] = Field(default_factory=dict)


class ReadListResult(BaseModel):
    list_id: str = ""
    list_name: str = ""
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
    total: int = 0
    rows: list[ReadListRow] = Field(default_factory=list)
    has_more: bool = False
    message: str = ""


def read_list_impl(
    *,
    organization_id: int,
    list_id: str,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> ReadListResult:
    org_list, records, page_num, cap, total = read_organization_list_records(
        organization_id=organization_id,
        list_id=list_id,
        page=page,
        page_size=page_size,
    )
    if org_list is None:
        return ReadListResult(message="List not found or import not ready.")

    rows: list[ReadListRow] = []
    for record in records:
        data = record.data if isinstance(record.data, dict) else {}
        rows.append(
            ReadListRow(
                position=record.position,
                data={str(k): str(v) for k, v in data.items()},
            )
        )

    end = page_num * cap
    has_more = end < total
    return ReadListResult(
        list_id=str(org_list.id),
        list_name=org_list.name,
        page=page_num,
        page_size=cap,
        total=total,
        rows=rows,
        has_more=has_more,
        message=f"{len(rows)} row(s) on page {page_num} of {total} total.",
    )


def get_tool(
    organization_id: int | None = None,
    **kwargs,
) -> dict:
    if organization_id is None:
        raise ValueError("read_list requires organization_id in tool context")

    org_id = int(organization_id)

    def read_list(
        list_id: str,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> ReadListResult:
        return read_list_impl(
            organization_id=org_id,
            list_id=list_id,
            page=page,
            page_size=page_size,
        )

    return {
        "name": "read_list",
        "description": (
            "Read rows from one organization uploaded list (CSV/Excel catalog) by list_id. "
            "Returns paginated cell data ordered as in the file. "
            "Use list_organization_lists first to discover list ids, columns, and record_count. "
            "Increase page when has_more is true. "
            "Do not walk every page of a large list unless required. "
            "For keyword lookup across rows, use list_search when that tool is enabled."
        ),
        "parameters": ReadListParams,
        "function": read_list,
    }
