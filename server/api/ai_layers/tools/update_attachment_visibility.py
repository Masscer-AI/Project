"""
Tool: update_attachment_visibility

Lets an agent that has this tool share a MessageAttachment with the
organization or selected roles. Gated by the agent's tool list, not by
whether the chatting user can change access in the UI.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from api.ai_layers.tools.attachment_access import (
    apply_attachment_ownership,
    attachment_belongs_to_payload,
    user_can_agent_update_attachment_visibility,
)

VisibilityChoice = Literal["personal", "organization", "roles", "link"]


class UpdateAttachmentVisibilityParams(BaseModel):
    attachment_id: str = Field(
        description="UUID from list_attachments or a generate_* tool result.",
    )
    visibility: VisibilityChoice = Field(
        description=(
            "personal: only the owner. "
            "organization: all members of the home organization. "
            "roles: members with the given role_ids. "
            "link: any member of the home organization (listed, not a secret URL)."
        ),
    )
    role_ids: list[str] | None = Field(
        default=None,
        description=(
            "Required when visibility is roles. Use list_organization_roles to "
            "discover role UUIDs."
        ),
    )


class UpdateAttachmentVisibilityResult(BaseModel):
    success: bool
    message: str
    attachment_id: str | None = None
    visibility: str | None = None
    belongs_to: dict = Field(default_factory=dict)


def _update_attachment_visibility_impl(
    *,
    attachment_id: str,
    visibility: VisibilityChoice,
    role_ids: list[str] | None,
    user_id: int,
) -> UpdateAttachmentVisibilityResult:
    from django.contrib.auth.models import User

    from api.messaging.models import MessageAttachment

    user = User.objects.filter(pk=int(user_id)).first()
    if user is None:
        raise ValueError("update_attachment_visibility requires an authenticated user")

    try:
        att = MessageAttachment.objects.select_related(
            "conversation", "organization", "user"
        ).prefetch_related("allowed_roles").get(id=attachment_id)
    except MessageAttachment.DoesNotExist:
        raise ValueError(f"Attachment {attachment_id} not found")

    if not user_can_agent_update_attachment_visibility(att, user):
        raise ValueError(
            f"Attachment {attachment_id} is not in your organization"
        )

    from api.compliance.folio import is_compliance_evidence

    if is_compliance_evidence(att):
        raise ValueError(
            "Compliance expediente files cannot have their visibility changed"
        )

    apply_attachment_ownership(
        att,
        user=user,
        visibility=visibility,
        role_ids=role_ids,
    )
    att.refresh_from_db()
    att = (
        MessageAttachment.objects.select_related("organization", "user")
        .prefetch_related("allowed_roles")
        .get(pk=att.pk)
    )
    vis = att.visibility or "personal"
    return UpdateAttachmentVisibilityResult(
        success=True,
        message=f"Attachment {att.id} visibility is now {vis}.",
        attachment_id=str(att.id),
        visibility=vis,
        belongs_to=attachment_belongs_to_payload(att, user),
    )


def get_tool(user_id: int | None = None, **kwargs) -> dict:
    if user_id is None:
        raise ValueError(
            "update_attachment_visibility requires user_id in tool context"
        )

    def update_attachment_visibility(
        attachment_id: str,
        visibility: VisibilityChoice,
        role_ids: list[str] | None = None,
    ) -> UpdateAttachmentVisibilityResult:
        return _update_attachment_visibility_impl(
            attachment_id=attachment_id,
            visibility=visibility,
            role_ids=role_ids,
            user_id=user_id,
        )

    return {
        "name": "update_attachment_visibility",
        "description": (
            "Share or unshare a file attachment. You may call this whenever this "
            "tool is enabled on the agent; the chatting user does not need UI "
            "permission to change access. Generated files start as personal; "
            "call this after generate_document_file / generate_excel_file / "
            "generate_gamma_attachment so other organization members (including "
            "linked WhatsApp contacts) can list and receive the file. "
            "visibility: personal, organization, or roles (needs role_ids from "
            "list_organization_roles). "
            "To send the file on WhatsApp, include "
            "[Download name](attachment:<attachment_id>) in the assistant reply."
        ),
        "parameters": UpdateAttachmentVisibilityParams,
        "function": update_attachment_visibility,
    }
