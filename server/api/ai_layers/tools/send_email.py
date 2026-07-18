"""
Tool: send_email

Sends HTML email to organization members via Resend.
Recipients are scoped user / role / organization targets (no free-form addresses).
"""

from __future__ import annotations

import base64
import logging
import re
from typing import Any, Literal

from django.conf import settings
from pydantic import BaseModel, Field

from api.authenticate.models import Organization
from api.authenticate.org_membership import (
    iter_organization_member_users,
    user_belongs_to_organization,
    users_with_role,
)
from api.utils.email_service import EmailAttachment, EmailService

logger = logging.getLogger(__name__)

_LOCAL_PART_RE = re.compile(r"[^a-z0-9._-]+")
_AGENT_SLUG_LOCAL_MAX_LEN = 25
_RESEND_MAX_RECIPIENTS = 50


class EmailRecipient(BaseModel):
    type: Literal["user", "role", "organization"]
    identifier: str | int | None = Field(
        default=None,
        description=(
            "user: Django user id (int). "
            "role: role UUID string. "
            "organization: omit or null (sends to all org members)."
        ),
    )


class SendEmailParams(BaseModel):
    subject: str = Field(description="Email subject line.")
    html: str = Field(description="HTML body for the email.")
    recipients: list[EmailRecipient] = Field(
        min_length=1,
        description=(
            "One or more org-scoped recipients. Combine user, role, and organization "
            "entries; duplicates are removed automatically."
        ),
    )
    attachment_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Optional MessageAttachment UUIDs from this conversation "
            "(documents, images, audio, video, spreadsheets, etc.)."
        ),
    )


class SendEmailResult(BaseModel):
    sent: bool
    message: str
    recipient_count: int = 0
    skipped_no_email_count: int = 0
    attachment_count: int = 0


def _normalize_recipients(
    recipients: list[EmailRecipient | dict[str, Any]],
) -> list[EmailRecipient]:
    """Agent loop passes model_dump() args; nested recipients arrive as dicts."""
    normalized: list[EmailRecipient] = []
    for item in recipients:
        if isinstance(item, EmailRecipient):
            normalized.append(item)
        elif isinstance(item, dict):
            normalized.append(EmailRecipient.model_validate(item))
        else:
            raise ValueError(f"Invalid recipient entry: {item!r}")
    return normalized


def _agent_from_local_part(agent_slug: str) -> str:
    slug = (agent_slug or "").strip().lower()[:_AGENT_SLUG_LOCAL_MAX_LEN]
    slug = _LOCAL_PART_RE.sub("", slug)
    slug = slug.strip(".-_")
    return slug[:_AGENT_SLUG_LOCAL_MAX_LEN] or "agent"


def _attachment_filename(att: Any) -> str:
    meta = getattr(att, "metadata", None) or {}
    if isinstance(meta, dict):
        for key in ("name", "filename", "output_filename"):
            value = (meta.get(key) or "").strip()
            if value:
                return value[:200]
    if att.file and att.file.name:
        return att.file.name.split("/")[-1][:200]
    return f"attachment-{att.id}"


def _load_email_attachment(
    attachment_id: str,
    *,
    conversation_id: str,
    user_id: int | None,
) -> EmailAttachment:
    from api.messaging.models import MessageAttachment

    try:
        att = MessageAttachment.objects.get(id=attachment_id)
    except MessageAttachment.DoesNotExist:
        raise ValueError(f"Attachment {attachment_id} not found")

    if str(att.conversation_id) != str(conversation_id):
        raise ValueError(
            f"Attachment {attachment_id} does not belong to this conversation"
        )

    if user_id is not None and att.user_id is not None and att.user_id != user_id:
        raise ValueError(f"Attachment {attachment_id} is not accessible")

    kind = getattr(att, "kind", None) or "file"
    if kind != "file":
        raise ValueError(
            f"Attachment {attachment_id} is not a file attachment and cannot be emailed"
        )

    if not att.file:
        raise ValueError(f"File content not available for attachment {attachment_id}")

    with att.file.open("rb") as f:
        raw = f.read()

    if not raw:
        raise ValueError(f"Attachment {attachment_id} is empty")

    return EmailAttachment(
        filename=_attachment_filename(att),
        content=base64.b64encode(raw).decode("ascii"),
    )


def _parse_user_id(identifier: str | int | None) -> int:
    if identifier is None:
        raise ValueError("Recipient type 'user' requires identifier (user id)")
    if isinstance(identifier, int):
        return identifier
    raw = str(identifier).strip()
    if not raw.isdigit():
        raise ValueError(f"Invalid user id: {identifier}")
    return int(raw)


def resolve_email_recipients(
    recipients: list[EmailRecipient | dict[str, Any]],
    organization: Organization,
) -> tuple[list[str], int]:
    from django.contrib.auth.models import User

    users_by_id: dict[int, User] = {}

    for recipient in _normalize_recipients(recipients):
        if recipient.type == "user":
            user_id = _parse_user_id(recipient.identifier)
            user = User.objects.filter(pk=user_id).first()
            if not user:
                raise ValueError(f"User {user_id} not found")
            if not user_belongs_to_organization(user, organization):
                raise ValueError(
                    f"User {user_id} is not a member of this organization"
                )
            users_by_id[user.id] = user
        elif recipient.type == "role":
            if not recipient.identifier:
                raise ValueError("Recipient type 'role' requires identifier (role UUID)")
            for user in users_with_role(organization.id, str(recipient.identifier)):
                users_by_id[user.id] = user
        elif recipient.type == "organization":
            for user in iter_organization_member_users(organization):
                users_by_id[user.id] = user
        else:
            raise ValueError(f"Unknown recipient type: {recipient.type}")

    deliverable: list[str] = []
    skipped_no_email = 0
    for user in users_by_id.values():
        email = (user.email or "").strip()
        if email:
            deliverable.append(email)
        else:
            skipped_no_email += 1

    if not deliverable:
        raise ValueError("No recipients with email addresses found")

    return deliverable, skipped_no_email


def _send_email_impl(
    *,
    subject: str,
    html: str,
    recipients: list[EmailRecipient | dict[str, Any]],
    attachment_ids: list[str],
    conversation_id: str,
    user_id: int,
    agent_slug: str,
    organization_id: int,
) -> SendEmailResult:
    from api.ai_layers.models import Agent

    organization = Organization.objects.filter(pk=organization_id).first()
    if not organization:
        raise ValueError("Organization not found")

    agent = Agent.objects.filter(slug=agent_slug).first()
    if not agent:
        raise ValueError("Agent not found")

    to_addresses, skipped_no_email = resolve_email_recipients(recipients, organization)

    from_domain = (
        getattr(settings, "RESEND_FROM_DOMAIN", None) or "mail.masscer.ai"
    ).strip()
    local_part = _agent_from_local_part(agent.slug)
    from_email = f"{local_part}@{from_domain}"

    attachments: list[EmailAttachment] = []
    for attachment_id in attachment_ids:
        attachments.append(
            _load_email_attachment(
                attachment_id,
                conversation_id=conversation_id,
                user_id=user_id,
            )
        )

    try:
        service = EmailService()
    except ValueError as exc:
        raise ValueError("Email provider is not configured") from exc

    try:
        for i in range(0, len(to_addresses), _RESEND_MAX_RECIPIENTS):
            batch = to_addresses[i : i + _RESEND_MAX_RECIPIENTS]
            service.send_email(
                to=batch,
                html=html,
                subject=subject[:200],
                from_email=from_email,
                from_name=agent.name,
                attachments=attachments or None,
            )
    except Exception as exc:
        logger.exception(
            "send_email failed (user_id=%s, agent_slug=%s, org_id=%s)",
            user_id,
            agent_slug,
            organization_id,
        )
        raise ValueError(f"Failed to send email: {exc}") from exc

    count = len(to_addresses)
    return SendEmailResult(
        sent=True,
        message=f"Email sent to {count} recipient(s).",
        recipient_count=count,
        skipped_no_email_count=skipped_no_email,
        attachment_count=len(attachments),
    )


def get_tool(
    conversation_id: str | None = None,
    user_id: int | None = None,
    agent_slug: str | None = None,
    organization_id: int | None = None,
    **kwargs,
) -> dict:
    if not conversation_id:
        raise ValueError("send_email requires conversation_id in tool context")
    if user_id is None:
        raise ValueError("send_email requires user_id in tool context")
    if not agent_slug:
        raise ValueError("send_email requires agent_slug in tool context")
    if organization_id is None:
        raise ValueError("send_email requires organization_id in tool context")

    from django.contrib.auth.models import User

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        raise ValueError("send_email requires an authenticated user")

    if not (user.email or "").strip():
        raise ValueError("send_email requires a user with an email address")

    def send_email(
        subject: str,
        html: str,
        recipients: list[EmailRecipient | dict[str, Any]],
        attachment_ids: list[str] | None = None,
    ) -> SendEmailResult:
        return _send_email_impl(
            subject=subject,
            html=html,
            recipients=recipients,
            attachment_ids=attachment_ids or [],
            conversation_id=conversation_id,
            user_id=user_id,
            agent_slug=agent_slug,
            organization_id=organization_id,
        )

    return {
        "name": "send_email",
        "description": (
            "Send an HTML email to organization members. "
            "Recipients are NOT email addresses — use list_organization_members and "
            "list_organization_roles first, then pass recipients as "
            "{type: user|role|organization, identifier: user_id|role_uuid|null}. "
            "Examples: email one member (type=user, identifier=<user_id>), "
            "a role (type=role, identifier=<role_id>), or everyone "
            "(type=organization, identifier=null). "
            "Combine multiple entries; duplicates are removed. "
            "Pass subject, html, and optional attachment_ids from this conversation. "
            "Use list_attachments for attachment IDs; generate files with "
            "generate_document_file or generate_excel_file when needed."
        ),
        "parameters": SendEmailParams,
        "function": send_email,
    }
