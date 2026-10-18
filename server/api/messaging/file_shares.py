from __future__ import annotations

from datetime import timedelta

from django.db.models import F, Q
from django.http import FileResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from api.ai_layers.mcp_access import public_app_base_url
from api.authenticate.tenant_services import (
    build_public_tenant_config,
    get_tenant_for_organization,
)
from api.rag.access import resolve_user_organization

from .attachment_access import user_can_access_attachment
from .models import FileShare, MessageAttachment, attachment_display_name

FILE_SHARE_DEFAULT_DAYS = 7
FILE_SHARE_MIN_DAYS = 1
FILE_SHARE_MAX_DAYS = 30


def file_share_url(share: FileShare) -> str:
    return f"{public_app_base_url()}/d/{share.id}"


def file_share_branding(share: FileShare, request) -> dict:
    tenant = get_tenant_for_organization(share.organization) if share.organization else None
    return build_public_tenant_config(tenant, request) if tenant else {}


def file_share_status(share: FileShare) -> str:
    if share.expires_at <= timezone.now():
        return "expired"
    if share.max_downloads is not None and share.download_count >= share.max_downloads:
        return "limit_reached"
    return "active"


def create_file_share(
    *,
    user,
    attachment_ids: list[str],
    expires_in_days: int = FILE_SHARE_DEFAULT_DAYS,
    max_downloads: int | None = None,
    conversation_id: str | None = None,
) -> FileShare:
    unique_ids = list(dict.fromkeys(str(a) for a in attachment_ids))
    attachments = list(MessageAttachment.objects.filter(id__in=unique_ids))
    found = {str(a.id) for a in attachments}
    missing = [a for a in unique_ids if a not in found]
    if missing:
        raise ValueError(f"Attachments not found: {', '.join(missing)}")

    for att in attachments:
        if att.kind != "file" or not att.file:
            raise ValueError(f"Attachment {att.id} is not a downloadable file")
        if not user_can_access_attachment(
            att, user=user, conversation_id=conversation_id
        ):
            raise ValueError(f"Attachment {att.id} is not available to you")

    share = FileShare.objects.create(
        user=user,
        organization=resolve_user_organization(user),
        conversation_id=conversation_id,
        expires_at=timezone.now() + timedelta(days=expires_in_days),
        max_downloads=max_downloads,
    )
    share.attachments.set(attachments)
    return share


@require_GET
def file_share_detail(request, share_id):
    share = FileShare.objects.select_related("organization").filter(id=share_id).first()
    if share is None:
        return JsonResponse({"message": "File share not found", "status": 404}, status=404)

    status = file_share_status(share)
    files = []
    if status == "active":
        files = [
            {
                "id": str(att.id),
                "name": attachment_display_name(att),
                "content_type": att.content_type or "",
            }
            for att in share.attachments.order_by("created_at")
        ]
    return JsonResponse(
        {
            "id": str(share.id),
            "status": status,
            "organization_name": share.organization.name if share.organization else "",
            "expires_at": share.expires_at.isoformat(),
            "max_downloads": share.max_downloads,
            "download_count": share.download_count,
            "files": files,
            "branding": file_share_branding(share, request),
        }
    )


@require_GET
def file_share_download(request, share_id, attachment_id):
    att = MessageAttachment.objects.filter(
        id=attachment_id, file_shares__id=share_id
    ).first()
    if att is None:
        return JsonResponse({"message": "File not found", "status": 404}, status=404)

    consumed = (
        FileShare.objects.filter(id=share_id, expires_at__gt=timezone.now())
        .filter(Q(max_downloads__isnull=True) | Q(download_count__lt=F("max_downloads")))
        .update(download_count=F("download_count") + 1)
    )
    if not consumed:
        return JsonResponse(
            {"message": "This link is no longer available", "status": 410}, status=410
        )

    return FileResponse(
        att.file.open("rb"),
        as_attachment=True,
        filename=attachment_display_name(att),
        content_type=att.content_type or "application/octet-stream",
    )
