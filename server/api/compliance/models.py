from __future__ import annotations

import uuid

from django.contrib.auth.models import User
from django.db import models


class FolioStatus(models.TextChoices):
    OPEN = "open", "Open"
    AWAITING_DOCUMENTS = "awaiting_documents", "Awaiting documents"
    IN_REVIEW = "in_review", "In review"
    NEEDS_CORRECTION = "needs_correction", "Needs correction"
    PENDING_SIGNATURE = "pending_signature", "Pending signature"
    CLEARED = "cleared", "Cleared"
    REJECTED = "rejected", "Rejected"
    ARCHIVED = "archived", "Archived"


class FolioDocumentStatus(models.TextChoices):
    UPLOADED = "uploaded", "Uploaded"
    VALIDATED = "validated", "Validated"
    REJECTED = "rejected", "Rejected"
    EXPIRED = "expired", "Expired"
    SUPERSEDED = "superseded", "Superseded"


class FolioEventType(models.TextChoices):
    FOLIO_CREATED = "folio_created", "Folio created"
    FOLIO_STATUS_CHANGED = "folio_status_changed", "Folio status changed"
    DOCUMENT_UPLOADED = "document_uploaded", "Document uploaded"
    DOCUMENT_UPDATED = "document_updated", "Document updated"
    NOTES_UPDATED = "notes_updated", "Notes updated"


class ComplianceFolio(models.Model):
    """KYB expediente for one subject user in one organization."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "authenticate.Organization",
        on_delete=models.CASCADE,
        related_name="compliance_folios",
    )
    subject_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="compliance_folios",
        help_text="Invited counterparty this expediente belongs to.",
    )
    status = models.CharField(
        max_length=32,
        choices=FolioStatus.choices,
        default=FolioStatus.OPEN,
        db_index=True,
    )
    notes = models.TextField(
        blank=True,
        default="",
        help_text="Working summary for the compliance agent (replaceable).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Compliance folio"
        verbose_name_plural = "Compliance folios"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "subject_user"],
                name="unique_compliance_folio_per_org_user",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "status"]),
        ]
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Folio({self.id}, {self.subject_user_id}, {self.status})"


class FolioDocument(models.Model):
    """One evidence file on a folio. Bytes live on MessageAttachment."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    folio = models.ForeignKey(
        ComplianceFolio,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    attachment = models.OneToOneField(
        "messaging.MessageAttachment",
        on_delete=models.PROTECT,
        related_name="folio_document",
        help_text="Chat file that holds the uploaded bytes.",
    )
    document_kind = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Checklist type (e.g. ine, constancia_fiscal). Empty until classified.",
    )
    status = models.CharField(
        max_length=32,
        choices=FolioDocumentStatus.choices,
        default=FolioDocumentStatus.UPLOADED,
        db_index=True,
    )
    notes = models.TextField(
        blank=True,
        default="",
        help_text="Why rejected, what is missing, validation notes.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Folio document"
        verbose_name_plural = "Folio documents"
        indexes = [
            models.Index(fields=["folio", "status"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"FolioDocument({self.id}, {self.document_kind or 'unspecified'}, {self.status})"


class FolioEvent(models.Model):
    """Append-only audit trail for a folio."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    folio = models.ForeignKey(
        ComplianceFolio,
        on_delete=models.CASCADE,
        related_name="events",
    )
    folio_document = models.ForeignKey(
        FolioDocument,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    event_type = models.CharField(max_length=32, choices=FolioEventType.choices)
    payload = models.JSONField(blank=True, default=dict)
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="compliance_folio_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Folio event"
        verbose_name_plural = "Folio events"
        indexes = [
            models.Index(fields=["folio", "event_type"]),
        ]
        ordering = ["created_at"]

    def __str__(self):
        return f"FolioEvent({self.event_type}, {self.folio_id})"


class PLDPersonType(models.TextChoices):
    PERSONA_FISICA = "persona_fisica", "Persona fisica"
    PERSONA_MORAL = "persona_moral", "Persona moral"


class PLDRelationship(models.TextChoices):
    CLIENTE = "cliente", "Cliente"
    PROVEEDOR = "proveedor", "Proveedor"
    AMBOS = "ambos", "Cliente y proveedor"


class VulnerableActivity(models.TextChoices):
    ACTIVOS_VIRTUALES = "activos_virtuales", "Activos virtuales"
    MUTUO_PRESTAMO = "mutuo_prestamo", "Mutuo, prestamo o credito"
    INMUEBLES = "inmuebles", "Inmuebles"
    VEHICULOS = "vehiculos", "Vehiculos"
    DONATIVOS = "donativos", "Donativos"
    COMERCIO_EXTERIOR = "comercio_exterior", "Comercio exterior"
    OTHER = "other", "Otra"


class PLDExpedientStatus(models.TextChoices):
    DATA_COLLECTION = "data_collection", "Data collection"
    DOCUMENT_COLLECTION = "document_collection", "Document collection"
    CROSS_REFERENCE = "cross_reference", "Cross reference"
    WAITING_SIGN = "waiting_sign", "Waiting signature"
    SIGNED = "signed", "Signed"
    DELIVERED = "delivered", "Delivered"
    ACTION_REQUIRED = "action_required", "Action required"


class PLDEntity(models.Model):
    """Directory row: the organization itself or a cliente/proveedor."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "authenticate.Organization",
        on_delete=models.CASCADE,
        related_name="pld_entities",
    )
    person_type = models.CharField(max_length=32, choices=PLDPersonType.choices)
    relationship = models.CharField(
        max_length=32,
        choices=PLDRelationship.choices,
        null=True,
        blank=True,
        help_text="Null means this row is the organization itself.",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pld_entities",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "PLD entity"
        verbose_name_plural = "PLD entities"
        constraints = [
            models.UniqueConstraint(
                fields=["organization"],
                condition=models.Q(relationship__isnull=True),
                name="unique_pld_self_entity_per_org",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "relationship"]),
        ]
        ordering = ["-updated_at"]

    def clean(self):
        from django.core.exceptions import ValidationError

        from api.compliance.pld_metadata import normalize_pld_entity_metadata

        try:
            self.metadata = normalize_pld_entity_metadata(
                self.person_type, self.metadata
            )
        except ValueError as exc:
            raise ValidationError({"metadata": str(exc)}) from exc

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        rel = self.relationship or "self"
        return f"PLDEntity({self.id}, {rel}, {self.person_type})"


class PLDExpedient(models.Model):
    """PLD process instance for one entity in an organization."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "authenticate.Organization",
        on_delete=models.CASCADE,
        related_name="pld_expedients",
    )
    entity = models.ForeignKey(
        PLDEntity,
        on_delete=models.CASCADE,
        related_name="expedients",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    vulnerable_activity = models.CharField(
        max_length=64,
        choices=VulnerableActivity.choices,
        blank=True,
        default="",
    )
    status = models.CharField(
        max_length=32,
        choices=PLDExpedientStatus.choices,
        default=PLDExpedientStatus.DATA_COLLECTION,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "PLD expedient"
        verbose_name_plural = "PLD expedients"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "entity"],
                name="unique_pld_expedient_per_org_entity",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "status"]),
        ]
        ordering = ["-updated_at"]

    def __str__(self):
        return f"PLDExpedient({self.id}, {self.status})"
