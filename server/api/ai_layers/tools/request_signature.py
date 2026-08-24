"""
Tool: request_signature

Sends an already-generated PDF attachment to an internal signatory for
e-signature via Mifiel (NOM-151 conservation record). The actual upload to
Mifiel happens asynchronously in a Celery task; this tool only creates the
durable SignatureRequest row and enqueues that task.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DocumentKindLiteral = Literal[
    "internal_policy_manual",
    "risk_methodology",
    "kyc_file",
    "suspicious_activity_notice",
    "monthly_notice",
    "other",
]


class RequestSignatureParams(BaseModel):
    attachment_id: str = Field(
        description="UUID of the MessageAttachment (PDF) already present in this conversation that needs a signature."
    )
    document_kind: DocumentKindLiteral = Field(
        default="other",
        description="What kind of compliance document this is.",
    )
    signatory_name: str = Field(description="Full name of the internal signatory.")
    signatory_email: str = Field(description="Email of the internal signatory (Mifiel sends the signing invite here).")
    signatory_rfc: str | None = Field(default=None, description="RFC of the signatory, if known.")
    title: str | None = Field(default=None, description="Short title for this document, shown in notifications.")


class RequestSignatureResult(BaseModel):
    signature_request_id: str
    status: str
    external_id: str
    signing_url: str


def _request_signature_impl(
    *,
    attachment_id: str,
    document_kind: str,
    signatory_name: str,
    signatory_email: str,
    signatory_rfc: str | None,
    title: str | None,
    conversation_id: str,
    organization_id: str | None,
    user_id: int | None,
) -> RequestSignatureResult:
    from django.conf import settings

    from api.esign.models import SignatureRequest, SignatureRequestStatus
    from api.esign.tasks import _notify_in_chat, submit_signature_request_to_mifiel
    from api.messaging.models import MessageAttachment

    if not organization_id:
        raise ValueError("request_signature requires an organization context.")

    signatory_name = (signatory_name or "").strip()
    if not signatory_name:
        raise ValueError("signatory_name is required.")

    signatory_email = (signatory_email or "").strip()
    if not signatory_email or "@" not in signatory_email:
        raise ValueError("signatory_email must be a valid email address.")

    try:
        attachment = MessageAttachment.objects.select_related("conversation").get(
            id=attachment_id
        )
    except MessageAttachment.DoesNotExist as exc:
        raise ValueError("Attachment not found.") from exc

    if str(attachment.conversation_id) != str(conversation_id):
        raise ValueError("Attachment does not belong to this conversation.")

    if not attachment.file:
        raise ValueError("Attachment has no underlying file.")

    filename = attachment.file.name or ""
    is_pdf = filename.lower().endswith(".pdf") or attachment.content_type == "application/pdf"
    if not is_pdf:
        raise ValueError("Only PDF attachments can be sent for signature via Mifiel.")

    if attachment.file.size > 20 * 1024 * 1024:
        raise ValueError("Mifiel accepts PDFs up to 20 MB; this attachment is larger.")

    signature_request = SignatureRequest.objects.create(
        organization_id=organization_id,
        requested_by_id=user_id,
        document_kind=document_kind,
        title=(title or "").strip(),
        signatory_name=signatory_name,
        signatory_email=signatory_email,
        signatory_rfc=(signatory_rfc or "").strip(),
        source_file=attachment,
        status=SignatureRequestStatus.PENDING,
    )

    submit_signature_request_to_mifiel.delay(str(signature_request.id))

    frontend_url = (getattr(settings, "FRONTEND_URL", "") or "").rstrip("/")
    signing_url = f"{frontend_url}/esign/sign/{signature_request.id}"

    _notify_in_chat(
        signature_request,
        text=(
            f"Comparte este enlace con {signatory_name} para firmar "
            f"«{signature_request.title or signature_request.get_document_kind_display()}»: "
            f"{signing_url}"
        ),
        attachment_ids=[],
    )

    logger.info(
        "Created SignatureRequest %s for attachment %s (org=%s)",
        signature_request.id,
        attachment_id,
        organization_id,
    )

    return RequestSignatureResult(
        signature_request_id=str(signature_request.id),
        status=signature_request.status,
        external_id=str(signature_request.external_id),
        signing_url=signing_url,
    )


def get_tool(
    conversation_id: str | None = None,
    organization_id: str | None = None,
    user_id: int | None = None,
    **kwargs,
) -> dict:
    if not conversation_id:
        raise ValueError("request_signature requires conversation_id in tool context")
    if not organization_id:
        raise ValueError("request_signature requires organization_id in tool context")

    def request_signature(
        attachment_id: str,
        signatory_name: str,
        signatory_email: str,
        document_kind: DocumentKindLiteral = "other",
        signatory_rfc: str | None = None,
        title: str | None = None,
    ) -> RequestSignatureResult:
        return _request_signature_impl(
            attachment_id=attachment_id,
            document_kind=document_kind,
            signatory_name=signatory_name,
            signatory_email=signatory_email,
            signatory_rfc=signatory_rfc,
            title=title,
            conversation_id=conversation_id,
            organization_id=organization_id,
            user_id=user_id,
        )

    return {
        "name": "request_signature",
        "description": (
            "Send a PDF attachment already present in this conversation to an internal "
            "signatory for legally-binding e-signature (Mifiel, with NOM-151 conservation "
            "record). Pass attachment_id from a document generated or uploaded earlier in "
            "this conversation, plus the signatory's name and email. A link to sign the "
            "document directly (no Mifiel account needed) is posted into this conversation "
            "automatically — no need to relay it yourself. The signed PDF and XML are "
            "attached back to this conversation automatically once signed."
        ),
        "parameters": RequestSignatureParams,
        "function": request_signature,
    }
