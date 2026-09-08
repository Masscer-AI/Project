from __future__ import annotations

import logging
from html import escape

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from datetime import timedelta

from api.compliance.clarifications import has_open_requests
from api.compliance.invites import entity_display_name
from api.compliance.models import PLDClarificationRequest, PLDExpedient, PLDExpedientStatus
from api.compliance.packet.pdf import build_identification_packet_pdf
from api.compliance.packet.signatory import resolve_signatories

logger = logging.getLogger(__name__)


def maybe_dispatch_identification_packet(expedient: PLDExpedient) -> None:
    """After a clear list screening, build the packet and send it for signature."""
    if expedient.status != PLDExpedientStatus.CROSS_REFERENCE:
        return
    if has_open_requests(expedient, PLDClarificationRequest.Stage.SCREENING):
        return
    payload = (
        expedient.screening_payload
        if isinstance(expedient.screening_payload, dict)
        else {}
    )
    if payload.get("verdict") != "clear":
        return
    if expedient.signature_request_id:
        return

    entity = expedient.entity
    signers = resolve_signatories(entity)
    if not signers:
        logger.warning(
            "PLD expedient %s is clear but has no signatories with email",
            expedient.id,
        )
        return

    pdf_bytes = build_identification_packet_pdf(entity)
    name = entity_display_name(entity)
    filename = "expediente-identificacion.pdf"
    expedient.packet_file.save(filename, ContentFile(pdf_bytes, name=filename), save=False)
    expedient.packet_generated_at = timezone.now()

    from api.esign.models import (
        SignatureDocumentKind,
        SignatureRequest,
        SignatureRequestStatus,
        SignatureSigner,
    )
    from api.esign.tasks import submit_signature_request_to_mifiel

    primary = signers[0]
    signature_request = SignatureRequest.objects.create(
        organization=expedient.organization,
        requested_by=getattr(expedient.organization, "owner", None),
        document_kind=SignatureDocumentKind.KYC_FILE,
        title=f"Expediente de identificacion — {name}"[:255],
        signatory_name=primary["name"],
        signatory_email=primary["email"],
        signatory_rfc=primary["rfc"],
        signatory_user=primary.get("user"),
        source_file=None,
        status=SignatureRequestStatus.PENDING,
        expires_at=timezone.now() + timedelta(days=30),
    )
    for row in signers:
        SignatureSigner.objects.create(
            signature_request=signature_request,
            role=row["role"],
            name=row["name"],
            email=row["email"],
            rfc=row["rfc"],
        )
    expedient.signature_request = signature_request
    expedient.status = PLDExpedientStatus.WAITING_SIGN
    expedient.save(
        update_fields=[
            "packet_file",
            "packet_generated_at",
            "signature_request",
            "status",
            "updated_at",
        ]
    )
    submit_signature_request_to_mifiel.delay(str(signature_request.id))
    logger.info(
        "Dispatched identification packet for expedient %s as SignatureRequest %s (%s signers)",
        expedient.id,
        signature_request.id,
        len(signers),
    )


def signing_url_for(signature_request, signer=None) -> str:
    frontend_url = (getattr(settings, "FRONTEND_URL", "") or "").rstrip("/")
    token = signer.id if signer is not None else signature_request.id
    return f"{frontend_url}/esign/sign/{token}"


def invitee_signing_payload(expedient: PLDExpedient, entity) -> dict | None:
    sr = expedient.signature_request
    if not sr:
        return None
    signers = list(sr.signers.all())
    email = (
        (entity.email or "").strip()
        or (getattr(entity.user, "email", "") or "")
    ).casefold()
    mine = None
    if email:
        mine = next((row for row in signers if row.email.casefold() == email), None)
    if mine is None and signers:
        mine = signers[0]
    return {
        "status": sr.status,
        "url": signing_url_for(sr, mine),
        "title": sr.title or "",
        "signer_count": len(signers) or 1,
        "you_signed": bool(mine and mine.status == "signed"),
    }


def mark_expedient_signed(signature_request, *, pdf_bytes: bytes, xml_bytes: bytes) -> None:
    expedient = PLDExpedient.objects.filter(signature_request=signature_request).first()
    if not expedient:
        return
    expedient.signed_packet.save(
        "expediente-identificacion-firmado.pdf",
        ContentFile(pdf_bytes, name="expediente-identificacion-firmado.pdf"),
        save=False,
    )
    expedient.signed_packet_xml.save(
        "expediente-identificacion-firmado.xml",
        ContentFile(xml_bytes, name="expediente-identificacion-firmado.xml"),
        save=False,
    )
    expedient.status = PLDExpedientStatus.DELIVERED
    expedient.save(
        update_fields=[
            "signed_packet",
            "signed_packet_xml",
            "status",
            "updated_at",
        ]
    )


def email_signing_links(signature_request) -> None:
    from api.utils.email_service import EmailService

    org_name = signature_request.organization.name
    title = signature_request.title or signature_request.get_document_kind_display()
    signers = list(signature_request.signers.all())
    if not signers:
        signers = [
            type(
                "Row",
                (),
                {
                    "id": signature_request.id,
                    "name": signature_request.signatory_name,
                    "email": signature_request.signatory_email,
                },
            )()
        ]
    others = len(signers)
    service = EmailService()
    for signer in signers:
        url = signing_url_for(signature_request, signer)
        org = escape(org_name)
        safe_url = escape(url, quote=True)
        extra = ""
        if others > 1:
            extra = (
                f"<p>Este mismo documento lo firman {others} personas. "
                "Tu enlace es personal; no lo reenvies.</p>"
            )
        html = f"""
            <div style="font-family: Arial, sans-serif; line-height: 1.5; color:#222;">
                <h2>Firma el expediente de identificacion</h2>
                <p>Hola {escape(signer.name)},</p>
                <p>
                    <strong>{org}</strong> necesita tu firma electronica sobre
                    «{escape(title)}». El enlace queda disponible 30 dias.
                </p>
                {extra}
                <p>
                    <a href="{safe_url}" style="display:inline-block;padding:10px 16px;background:#6e5bff;color:#fff;text-decoration:none;border-radius:6px;">
                        Firmar expediente
                    </a>
                </p>
                <p>Si el boton no funciona, abre este enlace cuando quieras:</p>
                <p><a href="{safe_url}">{safe_url}</a></p>
            </div>
        """.strip()
        try:
            service.send_email(
                to=signer.email,
                subject=f"Firma el expediente con {org_name}",
                html=html,
                from_name="Masscer",
            )
        except Exception:
            logger.exception(
                "Failed to email signing link to %s for SignatureRequest %s",
                signer.email,
                signature_request.id,
            )
