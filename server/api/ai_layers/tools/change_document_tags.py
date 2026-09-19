"""
Tool: change_document_tags

Replace knowledge-base document tag_ids (org catalog, max 3).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.ai_layers.tools.change_conversation_tags import MAX_TAGS
from api.messaging.organization_tags import apply_tag_ids, normalize_tag_ids


class ChangeDocumentTagsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: int = Field(description="Numeric knowledge-base document id.")
    tag_ids: list[int] = Field(
        default_factory=list,
        description=f"Tag IDs to set (0–{MAX_TAGS}). Replaces the previous list.",
    )

    @field_validator("tag_ids")
    @classmethod
    def cap_tag_ids(cls, v: list[int]) -> list[int]:
        return normalize_tag_ids(v)


class ChangeDocumentTagsResult(BaseModel):
    success: bool
    message: str
    document_id: int | None = None
    tag_ids: list[int] = Field(default_factory=list)


def _change_document_tags_impl(
    *,
    user_id: int,
    document_id: int,
    tag_ids: list[int],
) -> ChangeDocumentTagsResult:
    from django.contrib.auth.models import User

    from api.rag.access import resolve_user_organization, user_can_manage_document
    from api.rag.models import Document

    user = User.objects.filter(pk=int(user_id)).first()
    if user is None:
        return ChangeDocumentTagsResult(
            success=False, message="User not found.", document_id=document_id
        )
    try:
        doc = Document.objects.get(id=int(document_id))
    except Document.DoesNotExist:
        return ChangeDocumentTagsResult(
            success=False, message="Document not found.", document_id=document_id
        )
    if not user_can_manage_document(user, doc):
        return ChangeDocumentTagsResult(
            success=False,
            message="Document not accessible.",
            document_id=document_id,
        )
    org_id = doc.organization_id
    if not org_id:
        org = resolve_user_organization(user)
        org_id = org.id if org else None
    try:
        ordered = apply_tag_ids(
            doc,
            organization_id=org_id,
            tag_ids=tag_ids,
            strict=True,
        )
    except ValueError as exc:
        return ChangeDocumentTagsResult(
            success=False, message=str(exc), document_id=document_id
        )
    return ChangeDocumentTagsResult(
        success=True,
        message=f"Document tags set to {len(ordered)} tag(s).",
        document_id=doc.id,
        tag_ids=ordered,
    )


def get_tool(user_id: int | None = None, **kwargs) -> dict:
    if user_id is None:
        raise ValueError("change_document_tags requires user_id in tool context")

    def change_document_tags(
        document_id: int, tag_ids: list[int] | None = None
    ) -> ChangeDocumentTagsResult:
        return _change_document_tags_impl(
            user_id=int(user_id),
            document_id=int(document_id),
            tag_ids=list(tag_ids or []),
        )

    return {
        "name": "change_document_tags",
        "description": (
            "Set organization tags on a knowledge-base document (max 3 ids, replaces previous). "
            "Use tag ids from query_organization_tags. Empty list clears tags."
        ),
        "parameters": ChangeDocumentTagsParams,
        "function": change_document_tags,
    }
