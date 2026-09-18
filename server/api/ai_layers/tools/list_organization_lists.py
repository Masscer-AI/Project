"""
Tool: list_organization_lists

Catalog of organization uploaded lists (CSV/Excel) for list_search and read_list.
Auto-injected when list_search is enabled; not shown in tool pickers.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ListOrganizationListsParams(BaseModel):
    query: str | None = Field(
        default=None,
        description="Optional filter on list name or description (case-insensitive).",
    )


def _list_impl(
    *,
    organization_id: int,
    query: str | None = None,
) -> str:
    from django.db.models import Q

    from api.org_lists.models import OrganizationList

    qs = OrganizationList.objects.filter(
        organization_id=organization_id,
        import_status=OrganizationList.ImportStatus.SUCCEEDED,
    ).order_by("name")

    q = (query or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))

    items: list[dict[str, Any]] = []
    for org_list in qs[:100]:
        config = org_list.config if isinstance(org_list.config, dict) else {}
        columns_raw = config.get("columns") if isinstance(config.get("columns"), list) else []
        columns = []
        for col in columns_raw:
            if not isinstance(col, dict):
                continue
            name = str(col.get("name") or "").strip()
            if not name:
                continue
            columns.append(
                {
                    "name": name,
                    "examples": col.get("examples") if isinstance(col.get("examples"), list) else [],
                    "can_be_empty": bool(col.get("can_be_empty")),
                }
            )
        items.append(
            {
                "id": str(org_list.id),
                "name": org_list.name,
                "description": org_list.description or "",
                "record_count": org_list.record_count,
                "columns": columns,
            }
        )

    return json.dumps(
        {"count": len(items), "lists": items},
        ensure_ascii=False,
    )


def get_tool(
    organization_id: int | None = None,
    **kwargs,
) -> dict:
    if organization_id is None:
        raise ValueError("list_organization_lists requires organization_id in tool context")

    org_id = int(organization_id)

    def list_organization_lists(query: str | None = None) -> str:
        return _list_impl(organization_id=org_id, query=query)

    return {
        "name": "list_organization_lists",
        "description": (
            "List organization uploaded tabular lists (products, catalogs, etc.) "
            "that are ready to search. Returns id, name, description, record_count, "
            "and column metadata. Call before list_search or read_list when you need a list_id."
        ),
        "parameters": ListOrganizationListsParams,
        "function": list_organization_lists,
    }
