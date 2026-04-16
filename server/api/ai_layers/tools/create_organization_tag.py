"""
Tool: create_organization_tag

Creates a new Tag row for the organization when existing tags are not a good fit.
"""

from __future__ import annotations

import logging
import re

from django.db import IntegrityError
from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.messaging.models import Tag

logger = logging.getLogger(__name__)

_HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class CreateOrganizationTagParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(
        min_length=1,
        max_length=50,
        description="Short label for the tag (unique per organization, max 50 characters).",
    )
    description: str = Field(
        default="",
        description="Optional longer description to help future classification.",
    )
    color: str = Field(
        default="#4a9eff",
        description="Hex color for the tag, e.g. #4a9eff or #RGB.",
    )

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("title cannot be blank")
        return s

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        if not v or not _HEX_COLOR.match(v.strip()):
            raise ValueError("color must be a hex string like #RRGGBB or #RGB")
        return v.strip()


class CreateOrganizationTagResult(BaseModel):
    success: bool
    message: str
    tag_id: int | None = None
    title: str = ""


def _create_organization_tag_impl(
    organization_id: int,
    title: str,
    description: str,
    color: str,
) -> CreateOrganizationTagResult:
    try:
        tag = Tag.objects.create(
            organization_id=organization_id,
            title=title[:50],
            description=description or "",
            color=color,
            enabled=True,
        )
        logger.info(
            "create_organization_tag: id=%s org=%s title=%r",
            tag.id,
            organization_id,
            tag.title,
        )
        return CreateOrganizationTagResult(
            success=True,
            message="Tag created.",
            tag_id=tag.id,
            title=tag.title,
        )
    except IntegrityError:
        return CreateOrganizationTagResult(
            success=False,
            message=(
                "A tag with this title already exists for this organization. "
                "Call query_organization_tags and reuse the existing id, or pick a different title."
            ),
        )


def get_tool(organization_id: int | None = None, **kwargs) -> dict:
    if organization_id is None:
        raise ValueError("create_organization_tag requires organization_id in context")

    def create_organization_tag(
        title: str,
        description: str = "",
        color: str = "#4a9eff",
    ) -> CreateOrganizationTagResult:
        return _create_organization_tag_impl(
            organization_id=organization_id,
            title=title,
            description=description,
            color=color,
        )

    return {
        "name": "create_organization_tag",
        "description": (
            "Create a new organization tag when none of the existing tags fit the conversation topic. "
            "Prefer short, reusable titles. After creating, use change_conversation_tags to attach it."
        ),
        "parameters": CreateOrganizationTagParams,
        "function": create_organization_tag,
    }
