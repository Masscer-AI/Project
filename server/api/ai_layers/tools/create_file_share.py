"""
Tool: create_file_share

Creates a public, expiring download link for one or more MessageAttachment
files. Anyone with the link can download until it expires or hits
max_downloads; no login required.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from api.messaging.file_shares import (
    FILE_SHARE_DEFAULT_DAYS,
    FILE_SHARE_MAX_DAYS,
    FILE_SHARE_MIN_DAYS,
)


class CreateFileShareParams(BaseModel):
    attachment_ids: list[str] = Field(
        min_length=1,
        max_length=20,
        description="Attachment UUIDs from list_attachments or a generate_* tool result.",
    )
    expires_in_days: int = Field(
        default=FILE_SHARE_DEFAULT_DAYS,
        ge=FILE_SHARE_MIN_DAYS,
        le=FILE_SHARE_MAX_DAYS,
        description=(
            f"Days the link stays open ({FILE_SHARE_MIN_DAYS}-{FILE_SHARE_MAX_DAYS}). "
            f"Default {FILE_SHARE_DEFAULT_DAYS}."
        ),
    )
    max_downloads: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Optional cap on total file downloads by everyone with the link. "
            "Leave empty for no limit."
        ),
    )


class FileShareItem(BaseModel):
    attachment_id: str
    name: str


class CreateFileShareResult(BaseModel):
    success: bool
    message: str
    share_id: str
    url: str
    expires_at: str
    max_downloads: int | None = None
    files: list[FileShareItem] = Field(default_factory=list)


def _create_file_share_impl(
    *,
    attachment_ids: list[str],
    expires_in_days: int,
    max_downloads: int | None,
    user_id: int,
    conversation_id: str | None,
) -> CreateFileShareResult:
    from django.contrib.auth.models import User

    from api.messaging.file_shares import create_file_share, file_share_url
    from api.messaging.models import attachment_display_name
    from api.utils.timezone_utils import convert_to_organization_timezone

    user = User.objects.filter(pk=int(user_id)).first()
    if user is None:
        raise ValueError("create_file_share requires an authenticated user")

    share = create_file_share(
        user=user,
        attachment_ids=attachment_ids,
        expires_in_days=expires_in_days,
        max_downloads=max_downloads,
        conversation_id=conversation_id,
    )
    org_tz = share.organization.timezone if share.organization else "UTC"
    expires_at = convert_to_organization_timezone(share.expires_at, org_tz)
    files = [
        FileShareItem(attachment_id=str(att.id), name=attachment_display_name(att))
        for att in share.attachments.order_by("created_at")
    ]
    return CreateFileShareResult(
        success=True,
        message=f"Download link for {len(files)} file(s) is open until {expires_at.isoformat()}.",
        share_id=str(share.id),
        url=file_share_url(share),
        expires_at=expires_at.isoformat(),
        max_downloads=share.max_downloads,
        files=files,
    )


def get_tool(
    user_id: int | None = None,
    conversation_id: str | None = None,
    **kwargs,
) -> dict:
    if user_id is None:
        raise ValueError("create_file_share requires user_id in tool context")

    def create_file_share(
        attachment_ids: list[str],
        expires_in_days: int = FILE_SHARE_DEFAULT_DAYS,
        max_downloads: int | None = None,
    ) -> CreateFileShareResult:
        return _create_file_share_impl(
            attachment_ids=attachment_ids,
            expires_in_days=expires_in_days,
            max_downloads=max_downloads,
            user_id=user_id,
            conversation_id=conversation_id,
        )

    return {
        "name": "create_file_share",
        "description": (
            "Create a download link for one or more files. Anyone with the link "
            "can download the files until it expires or reaches max_downloads; "
            "no login needed. Only files you can access. "
            "Returns url and share_id. Send the url by email, chat, or any other "
            "channel. On WhatsApp, use the archivos_compartidos_es or "
            "shared_files_en template: pass share_id as the button value and "
            "the expiry date, written for people in the template's language, "
            "as {{3}}."
        ),
        "parameters": CreateFileShareParams,
        "function": create_file_share,
    }
