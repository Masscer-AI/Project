from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.core.files.base import ContentFile
from django.utils import timezone

from .mifiel_client import MifielAPIError, MifielClient
from .models import SignatureRequest, SignatureRequestEvent, SignatureRequestStatus

logger = logging.getLogger(__name__)


@shared_task
def submit_signature_request_to_mifiel(signature_request_id: str) -> None:
    try:
        signature_request = SignatureRequest.objects.select_related(
            "source_file"
        ).get(id=signature_request_id)
    except SignatureRequest.DoesNotExist:
        logger.error("SignatureRequest %s not found", signature_request_id)
        return

    source = signature_request.source_file
    if not source.file:
        signature_request.status = SignatureRequestStatus.ERROR
        signature_request.metadata = {
            **signature_request.metadata,
            "error": "source_file has no underlying file.",
        }
        signature_request.save(update_fields=["status", "metadata", "updated_at"])
        return

    filename = source.file.name.rsplit("/", 1)[-1] or "document.pdf"
    file_bytes = source.file.read()

    signatory = {
        "name": signature_request.signatory_name,
        "email": signature_request.signatory_email,
        "tax_id": signature_request.signatory_rfc or "",
    }

    try:
        response = MifielClient().create_document(
            file_bytes=file_bytes,
            filename=filename,
            signatories=[signatory],
            external_id=str(signature_request.external_id),
            # The embedded widget page (esign/views.py:PublicSignatureRequestView)
            # is the primary signing surface now, not Mifiel's own emailed link —
            # avoid a second, uncontrolled Mifiel-hosted signing page.
            send_invites=False,
        )
    except MifielAPIError as e:
        logger.error(
            "Mifiel create_document failed for SignatureRequest %s: %s",
            signature_request_id,
            e,
        )
        signature_request.status = SignatureRequestStatus.ERROR
        signature_request.metadata = {
            **signature_request.metadata,
            "error": str(e),
        }
        signature_request.save(update_fields=["status", "metadata", "updated_at"])
        return

    signers = response.get("signers") or []
    widget_id = signers[0].get("widget_id", "") if signers else ""
    if not widget_id:
        logger.warning(
            "Mifiel create_document returned no widget_id for SignatureRequest %s",
            signature_request_id,
        )

    signature_request.provider_document_id = response.get("id", "")
    signature_request.provider_widget_id = widget_id
    signature_request.metadata = {
        **signature_request.metadata,
        "create_response": response,
    }
    signature_request.save(
        update_fields=[
            "provider_document_id",
            "provider_widget_id",
            "metadata",
            "updated_at",
        ]
    )
    logger.info(
        "SignatureRequest %s submitted to Mifiel as document %s",
        signature_request_id,
        signature_request.provider_document_id,
    )


def _notify_in_chat(
    signature_request: SignatureRequest, text: str, attachments: list[dict]
) -> None:
    """
    Post a message into the conversation the source document came from.

    ``attachments`` must already be Message.attachments-shaped display dicts
    (e.g. {"type": ..., "content"/"name": ..., "attachment_id": ...}), not
    raw MessageAttachment IDs — Message.attachments is stored/serialized
    verbatim, so the frontend's Thumbnail component needs the full dict to
    render a card instead of a bare id string.
    """
    from api.messaging.models import Message
    from api.messaging.takeover import emit_message_created

    try:
        conversation = signature_request.source_file.conversation
        message = Message.objects.create(
            conversation=conversation,
            type="assistant",
            text=text,
            attachments=attachments,
            metadata={
                "source": "esign_mifiel",
                "signature_request_id": str(signature_request.id),
            },
        )
        emit_message_created(None, conversation, message)
    except Exception:
        logger.exception(
            "Failed to post in-chat notification for SignatureRequest %s",
            signature_request.id,
        )


def signing_link_attachment_dict(signature_request: SignatureRequest, url: str) -> dict:
    """
    Message.attachments-shaped descriptor for a Mifiel signing link. Rendered
    as a link card in the chat UI (Thumbnail.tsx, type === "signature_request")
    instead of a raw URL pasted into message text.
    """
    return {
        "type": "signature_request",
        "content": url,
        "name": signature_request.title or signature_request.get_document_kind_display(),
        "status": signature_request.status,
        "signatory_name": signature_request.signatory_name,
    }


def _handle_document_closed(signature_request: SignatureRequest, data: dict) -> None:
    from api.ai_layers.tasks import _message_attachment_to_display_dict
    from api.messaging.models import MessageAttachment

    if signature_request.status == SignatureRequestStatus.SIGNED:
        logger.info(
            "SignatureRequest %s already SIGNED, ignoring duplicate document_closed webhook.",
            signature_request.id,
        )
        return

    try:
        client = MifielClient()
        signed_pdf_bytes = client.download_signed_file(
            signature_request.provider_document_id, "file_signed"
        )
        signed_xml_bytes = client.download_signed_file(
            signature_request.provider_document_id, "file_signed_xml"
        )
    except MifielAPIError as e:
        logger.error(
            "Failed to download signed files for SignatureRequest %s: %s",
            signature_request.id,
            e,
        )
        signature_request.status = SignatureRequestStatus.ERROR
        signature_request.metadata = {
            **signature_request.metadata,
            "error": f"download_signed_file failed: {e}",
        }
        signature_request.save(update_fields=["status", "metadata", "updated_at"])
        return

    conversation = signature_request.source_file.conversation
    base_name = data.get("file_file_name") or "document"
    expires_at = timezone.now() + timedelta(days=365 * 10)

    signed_pdf = MessageAttachment.objects.create(
        conversation=conversation,
        agent=signature_request.source_file.agent,
        kind="file",
        file=ContentFile(signed_pdf_bytes, name=f"{base_name}-signed.pdf"),
        content_type="application/pdf",
        expires_at=expires_at,
        metadata={
            "source": "mifiel_document_closed",
            "signature_request_id": str(signature_request.id),
        },
    )
    signed_xml = MessageAttachment.objects.create(
        conversation=conversation,
        agent=signature_request.source_file.agent,
        kind="file",
        file=ContentFile(signed_xml_bytes, name=f"{base_name}-signed.xml"),
        content_type="application/xml",
        expires_at=expires_at,
        metadata={
            "source": "mifiel_document_closed",
            "signature_request_id": str(signature_request.id),
        },
    )

    signature_request.signed_file = signed_pdf
    signature_request.signed_file_xml = signed_xml
    signature_request.status = SignatureRequestStatus.SIGNED
    signature_request.signed_at = timezone.now()
    signature_request.save(
        update_fields=["signed_file", "signed_file_xml", "status", "signed_at", "updated_at"]
    )

    signed_attachments = [
        d
        for d in (
            _message_attachment_to_display_dict(signed_pdf),
            _message_attachment_to_display_dict(signed_xml),
        )
        if d is not None
    ]
    _notify_in_chat(
        signature_request,
        text=(
            f"El documento «{signature_request.title or signature_request.get_document_kind_display()}» "
            f"fue firmado por {signature_request.signatory_name} y quedó archivado "
            "con su constancia de conservación (NOM-151)."
        ),
        attachments=signed_attachments,
    )


def _handle_signer_rejected(signature_request: SignatureRequest) -> None:
    if signature_request.status in (
        SignatureRequestStatus.SIGNED,
        SignatureRequestStatus.REJECTED,
    ):
        return
    signature_request.status = SignatureRequestStatus.REJECTED
    signature_request.rejected_at = timezone.now()
    signature_request.save(update_fields=["status", "rejected_at", "updated_at"])
    _notify_in_chat(
        signature_request,
        text=(
            f"{signature_request.signatory_name} rechazó la firma del documento "
            f"«{signature_request.title or signature_request.get_document_kind_display()}»."
        ),
        attachments=[],
    )


def _handle_document_deleted(signature_request: SignatureRequest) -> None:
    signature_request.status = SignatureRequestStatus.DELETED
    signature_request.save(update_fields=["status", "updated_at"])


@shared_task
def process_mifiel_webhook_event(payload: dict) -> None:
    event = payload.get("event")
    data = payload.get("data") or {}
    # document_closed/document_deleted use "external_id"; signer_completed/
    # signer_rejected use "document_external_id" instead (per Mifiel's docs).
    external_id = data.get("external_id") or data.get("document_external_id")

    if not external_id:
        logger.warning("Mifiel webhook payload missing external_id, dropping: %s", payload)
        return

    try:
        signature_request = SignatureRequest.objects.select_related(
            "source_file", "source_file__conversation"
        ).get(external_id=external_id)
    except (SignatureRequest.DoesNotExist, ValueError):
        logger.warning(
            "Mifiel webhook external_id %s does not match any SignatureRequest, dropping.",
            external_id,
        )
        return

    SignatureRequestEvent.objects.create(
        signature_request=signature_request,
        event_type=event or "unknown",
        payload=payload,
    )

    if event == "document_closed":
        _handle_document_closed(signature_request, data)
    elif event == "signer_rejected":
        _handle_signer_rejected(signature_request)
    elif event == "document_deleted":
        _handle_document_deleted(signature_request)
    elif event == "signer_completed":
        pass  # event log row above is sufficient for v1 (single signatory).
    else:
        logger.warning("Unhandled Mifiel webhook event type: %s", event)
