from __future__ import annotations

import uuid

from django.contrib.auth.models import User
from django.db import models


class SignatureProvider(models.TextChoices):
    MIFIEL = "mifiel", "Mifiel"


class SignatureDocumentKind(models.TextChoices):
    INTERNAL_POLICY_MANUAL = "internal_policy_manual", "Manual de politicas internas"
    RISK_METHODOLOGY = "risk_methodology", "Metodologia EBR"
    KYC_FILE = "kyc_file", "Expediente KYC/KYB"
    SUSPICIOUS_ACTIVITY_NOTICE = "suspicious_activity_notice", "Aviso de 24 horas"
    MONTHLY_NOTICE = "monthly_notice", "Aviso mensual"
    OTHER = "other", "Otro"


class SignatureRequestStatus(models.TextChoices):
    PENDING = "pending", "Pendiente de firma"
    SIGNED = "signed", "Firmado"
    REJECTED = "rejected", "Rechazado"
    EXPIRED = "expired", "Expirado"
    DELETED = "deleted", "Eliminado"
    ERROR = "error", "Error"


class SignatureRequest(models.Model):
    """
    Tracks one document sent to an internal signatory for e-signature via a
    provider (Mifiel today). Mirrors the provider-side document lifecycle so
    Masscer can answer "is this signed yet?" without polling the provider API.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "authenticate.Organization",
        on_delete=models.CASCADE,
        related_name="signature_requests",
    )
    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="signature_requests_created",
    )

    provider = models.CharField(
        max_length=32,
        choices=SignatureProvider.choices,
        default=SignatureProvider.MIFIEL,
    )
    provider_document_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Document id returned by the provider (e.g. Mifiel document uuid).",
    )
    external_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text=(
            "Masscer-generated correlation id sent to the provider as external_id. "
            "Used to match inbound webhooks to this request without trusting the "
            "webhook payload alone."
        ),
    )

    document_kind = models.CharField(
        max_length=64,
        choices=SignatureDocumentKind.choices,
        default=SignatureDocumentKind.OTHER,
    )
    title = models.CharField(max_length=255, blank=True, default="")

    signatory_name = models.CharField(max_length=255)
    signatory_email = models.EmailField()
    signatory_rfc = models.CharField(max_length=13, blank=True, default="")
    signatory_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="signature_requests_to_sign",
        help_text="Internal user who must sign, when they have a Masscer account.",
    )

    source_file = models.ForeignKey(
        "messaging.MessageAttachment",
        on_delete=models.PROTECT,
        related_name="signature_requests_as_source",
        help_text="Unsigned PDF sent to the provider, as already generated/uploaded in a conversation.",
    )
    signed_file = models.ForeignKey(
        "messaging.MessageAttachment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="signature_requests_as_signed_pdf",
        help_text="Signed PDF, attached back to the source conversation after document_closed.",
    )
    signed_file_xml = models.ForeignKey(
        "messaging.MessageAttachment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="signature_requests_as_signed_xml",
        help_text="Legally-binding XML (with NOM-151 conservation record), attached after document_closed.",
    )

    status = models.CharField(
        max_length=20,
        choices=SignatureRequestStatus.choices,
        default=SignatureRequestStatus.PENDING,
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Free-form provider response snapshots, error details, etc.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["provider", "provider_document_id"]),
        ]

    def __str__(self) -> str:
        return f"SignatureRequest({self.document_kind}, {self.signatory_email}, status={self.status})"


class SignatureRequestEvent(models.Model):
    """
    Append-only log of every webhook received for a SignatureRequest. Kept
    separate from SignatureRequest's mutable status so the raw provider
    payload trail stays intact for audit purposes.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    signature_request = models.ForeignKey(
        SignatureRequest,
        on_delete=models.CASCADE,
        related_name="events",
    )
    event_type = models.CharField(
        max_length=32,
        help_text="Raw provider event name, e.g. document_closed, signer_completed.",
    )
    payload = models.JSONField(default=dict, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["received_at"]
        indexes = [
            models.Index(fields=["signature_request", "event_type"]),
        ]

    def __str__(self) -> str:
        return f"SignatureRequestEvent({self.event_type}, request={self.signature_request_id})"
