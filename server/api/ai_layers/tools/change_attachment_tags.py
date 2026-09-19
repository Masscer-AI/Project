"""
Tool: change_attachment_tags

Replace gallery/chat attachment tag_ids (org catalog, max 3).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.ai_layers.tools.change_conversation_tags import MAX_TAGS
from api.messaging.organization_tags import apply_tag_ids, normalize_tag_ids


class ChangeAttachmentTagsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attachment_id: str = Field(description="UUID from list_attachments.")
    tag_ids: list[int] = Field(
        default_factory=list,
        description=f"Tag IDs to set (0–{MAX_TAGS}). Replaces the previous list.",
    )

    @field_validator("tag_ids")
    @classmethod
    def cap_tag_ids(cls, v: list[int]) -> list[int]:
        return normalize_tag_ids(v)


class ChangeAttachmentTagsResult(BaseModel):
    success: bool
    message: str
    attachment_id: str | None = None
    tag_ids: list[int] = Field(default_factory=list)


def _change_attachment_tags_impl(
    *,
    user_id: int,
    attachment_id: str,
    tag_ids: list[int],
) -> ChangeAttachmentTagsResult:
    from django.contrib.auth.models import User

    from api.messaging.attachment_access import user_can_manage_attachment
    from api.messaging.gallery import _attachment_tag_org_id
    from api.messaging.models import MessageAttachment

    user = User.objects.filter(pk=int(user_id)).first()
    if user is None:
        return ChangeAttachmentTagsResult(
            success=False, message="User not found.", attachment_id=attachment_id
        )
    try:
        att = MessageAttachment.objects.select_related(
            "conversation", "organization"
        ).get(id=attachment_id)
    except MessageAttachment.DoesNotExist:
        return ChangeAttachmentTagsResult(
            success=False,
            message="Attachment not found.",
            attachment_id=attachment_id,
        )
    if not user_can_manage_attachment(att, user):
        return ChangeAttachmentTagsResult(
            success=False,
            message="Attachment not accessible.",
            attachment_id=attachment_id,
        )
    try:
        ordered = apply_tag_ids(
            att,
            organization_id=_attachment_tag_org_id(att, user),
            tag_ids=tag_ids,
            strict=True,
        )
    except ValueError as exc:
        return ChangeAttachmentTagsResult(
            success=False, message=str(exc), attachment_id=attachment_id
        )
    return ChangeAttachmentTagsResult(
        success=True,
        message=f"Attachment tags set to {len(ordered)} tag(s).",
        attachment_id=str(att.id),
        tag_ids=ordered,
    )


def get_tool(user_id: int | None = None, **kwargs) -> dict:
    if user_id is None:
        raise ValueError("change_attachment_tags requires user_id in tool context")

    def change_attachment_tags(
        attachment_id: str, tag_ids: list[int] | None = None
    ) -> ChangeAttachmentTagsResult:
        return _change_attachment_tags_impl(
            user_id=int(user_id),
            attachment_id=str(attachment_id),
            tag_ids=list(tag_ids or []),
        )

    return {
        "name": "change_attachment_tags",
        "description": (
            "Set organization tags on a chat/gallery attachment (max 3 ids, replaces previous). "
            "Use tag ids from query_organization_tags. Empty list clears tags."
        ),
        "parameters": ChangeAttachmentTagsParams,
        "function": change_attachment_tags,
    }
