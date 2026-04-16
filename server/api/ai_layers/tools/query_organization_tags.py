"""
Tool: query_organization_tags

Returns enabled tags for the current organization so the agent can reuse titles/IDs
or decide to create a new tag.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from api.messaging.models import Tag


class QueryOrganizationTagsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrganizationTagItem(BaseModel):
    id: int = Field(description="Tag primary key; use with change_conversation_tags")
    title: str
    description: str = ""
    color: str = ""
    enabled: bool = True


class QueryOrganizationTagsResult(BaseModel):
    tags: list[OrganizationTagItem] = Field(default_factory=list)
    message: str = Field(default="Listed organization tags")


def _query_organization_tags_impl(organization_id: int) -> QueryOrganizationTagsResult:
    qs = (
        Tag.objects.filter(organization_id=organization_id, enabled=True)
        .order_by("title")
        .values("id", "title", "description", "color", "enabled")
    )
    items = [
        OrganizationTagItem(
            id=row["id"],
            title=row["title"],
            description=row["description"] or "",
            color=row["color"] or "",
            enabled=bool(row["enabled"]),
        )
        for row in qs
    ]
    return QueryOrganizationTagsResult(
        tags=items,
        message=f"Found {len(items)} enabled tag(s) for this organization.",
    )


def get_tool(organization_id: int | None = None, **kwargs) -> dict:
    if organization_id is None:
        raise ValueError("query_organization_tags requires organization_id in context")

    def query_organization_tags() -> QueryOrganizationTagsResult:
        return _query_organization_tags_impl(organization_id)

    return {
        "name": "query_organization_tags",
        "description": (
            "List all enabled tags for this organization (id, title, description, color). "
            "Optional: the system prompt already includes this conversation’s current tags — "
            "only call this when you need the full org catalog (e.g. after creating a tag, or to compare many labels)."
        ),
        "parameters": QueryOrganizationTagsParams,
        "function": query_organization_tags,
    }
