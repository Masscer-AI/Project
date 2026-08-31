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
