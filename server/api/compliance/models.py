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
    email = models.EmailField(
        blank=True,
        default="",
        help_text="Contact email for expediente invitations. Empty for the org self-entity.",
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


def pld_expedient_packet_upload_to(instance, filename):
    import os

    ext = os.path.splitext(filename)[1].lower()[:12] or ".pdf"
    return f"pld_expedient_packets/{instance.id}/{uuid.uuid4()}{ext}"


class PLDExpedient(models.Model):
    """PLD process instance for one entity in an organization."""

    class PrequalificationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

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
    prequalification_status = models.CharField(
        max_length=16,
        choices=PrequalificationStatus.choices,
        blank=True,
        default="",
    )
    prequalification_payload = models.JSONField(default=dict, blank=True)
    prequalified_at = models.DateTimeField(null=True, blank=True)
    screening_status = models.CharField(
        max_length=16,
        choices=PrequalificationStatus.choices,
        blank=True,
        default="",
    )
    screening_payload = models.JSONField(default=dict, blank=True)
    screened_at = models.DateTimeField(null=True, blank=True)
    risk_status = models.CharField(
        max_length=16,
        choices=PrequalificationStatus.choices,
        blank=True,
        default="",
    )
    risk_payload = models.JSONField(default=dict, blank=True)
    risked_at = models.DateTimeField(null=True, blank=True)
    packet_file = models.FileField(
        upload_to=pld_expedient_packet_upload_to,
        blank=True,
        default="",
    )
    packet_generated_at = models.DateTimeField(null=True, blank=True)
    signed_packet = models.FileField(
        upload_to=pld_expedient_packet_upload_to,
        blank=True,
        default="",
    )
    signed_packet_xml = models.FileField(
        upload_to=pld_expedient_packet_upload_to,
        blank=True,
        default="",
    )
    signature_request = models.ForeignKey(
        "esign.SignatureRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pld_expedients",
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


def pld_expedient_document_upload_to(instance, filename):
    import os

    ext = os.path.splitext(filename)[1].lower()[:12]
    return f"pld_expedient_documents/{instance.expedient_id}/{uuid.uuid4()}{ext}"


class PLDExpedientDocument(models.Model):
    """Invitee-uploaded copy for one checklist slot on an expedient."""

    class ExtractionStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    expedient = models.ForeignKey(
        PLDExpedient,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    slot_key = models.CharField(max_length=64)
    document_kind = models.CharField(max_length=64)
    file = models.FileField(upload_to=pld_expedient_document_upload_to)
    original_filename = models.CharField(max_length=255, blank=True, default="")
    content_type = models.CharField(max_length=128, blank=True, default="")
    file_size = models.PositiveIntegerField(default=0)
    file_sha256 = models.CharField(max_length=64, blank=True, default="")
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pld_expedient_documents",
    )
    extraction_status = models.CharField(
        max_length=16,
        choices=ExtractionStatus.choices,
        blank=True,
        default="",
    )
    extracted_at = models.DateTimeField(null=True, blank=True)
    extracted_payload = models.JSONField(default=dict, blank=True)
    extraction_error = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "PLD expedient document"
        verbose_name_plural = "PLD expedient documents"
        constraints = [
            models.UniqueConstraint(
                fields=["expedient", "slot_key"],
                name="unique_pld_document_slot_per_expedient",
            ),
        ]
        indexes = [
            models.Index(
                fields=["expedient", "document_kind"],
                name="compliance__expedie_doc_idx",
            ),
        ]
        ordering = ["slot_key"]

    def __str__(self):
        return f"PLDExpedientDocument({self.slot_key}, {self.expedient_id})"


class PLDClarificationRequest(models.Model):
    """Invitee-facing question from identification or list-screening review."""

    class Stage(models.TextChoices):
        IDENTIFICATION = "identification", "Identification"
        SCREENING = "screening", "Screening"

    class AnswerType(models.TextChoices):
        TEXT = "text", "Text"
        DOCUMENT = "document", "Document"
        EITHER = "either", "Text or document"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ANSWERED = "answered", "Answered"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    expedient = models.ForeignKey(
        PLDExpedient,
        on_delete=models.CASCADE,
        related_name="clarification_requests",
    )
    stage = models.CharField(max_length=16, choices=Stage.choices, db_index=True)
    prompt = models.CharField(max_length=400)
    answer_type = models.CharField(
        max_length=16,
        choices=AnswerType.choices,
        default=AnswerType.TEXT,
    )
    target = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    text_answer = models.TextField(blank=True, default="")
    answered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "PLD clarification request"
        verbose_name_plural = "PLD clarification requests"
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["expedient", "stage", "status"],
                name="compliance__expedie_f67682_idx",
            ),
        ]

    def __str__(self):
        return f"PLDClarificationRequest({self.stage}, {self.status})"

    @property
    def slot_key(self) -> str:
        return f"clarify:{self.id}"


class PLDInvite(models.Model):
    """Invite a counterparty to complete a PLD expediente (not an org membership)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "authenticate.Organization",
        on_delete=models.CASCADE,
        related_name="pld_invites",
    )
    entity = models.ForeignKey(
        PLDEntity,
        on_delete=models.CASCADE,
        related_name="invites",
    )
    email = models.EmailField()
    invited_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="pld_invites_sent",
    )
    token_hash = models.CharField(max_length=64, unique=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    invite_expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accepted_pld_invites",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "PLD invite"
        verbose_name_plural = "PLD invites"
        constraints = [
            models.UniqueConstraint(
                fields=["entity"],
                condition=models.Q(status="pending"),
                name="unique_pending_pld_invite_per_entity",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["email", "status"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"PLDInvite<{self.email}>@{self.entity_id} ({self.status})"

    @staticmethod
    def generate_raw_token() -> str:
        import secrets

        return secrets.token_urlsafe(48)

    @classmethod
    def lookup_by_raw_token(cls, raw_token: str):
        if not raw_token:
            return None
        from api.authenticate.models import hash_organization_invite_token

        digest = hash_organization_invite_token(raw_token.strip())
        return (
            cls.objects.filter(token_hash=digest)
            .select_related("organization", "entity")
            .first()
        )

    def is_invite_expired(self, now=None):
        from django.utils import timezone

        now = now or timezone.now()
        return self.invite_expires_at <= now

    def mark_expired_if_needed(self, now=None):
        from django.utils import timezone

        now = now or timezone.now()
        if self.status == self.Status.PENDING and self.invite_expires_at <= now:
            self.status = self.Status.EXPIRED
            self.save(update_fields=["status", "updated_at"])
            return True
        return False


class WatchlistListSlug(models.TextChoices):
    ONU_CSNU = "onu_csnu", "ONU CSNU consolidated"
    SAT_69B = "sat_69b", "SAT Art. 69-B complete"
    SAT_69B_BIS = "sat_69b_bis", "SAT Art. 69-B Bis complete"
    SAT_69_FIRMES = "sat_69_firmes", "SAT Art. 69 firmes"
    SAT_69_NO_LOCALIZADOS = "sat_69_no_localizados", "SAT Art. 69 no localizados"
    SAT_69_EXIGIBLES = "sat_69_exigibles", "SAT Art. 69 exigibles"
    SAT_69_SENTENCIAS = "sat_69_sentencias", "SAT Art. 69 sentencias"
    SAT_69_CSD = "sat_69_csd", "SAT Art. 69 CSD sin efectos"


class WatchlistRecordType(models.TextChoices):
    INDIVIDUAL = "individual", "Individual"
    ENTITY = "entity", "Entity"


class WatchlistSnapshotStatus(models.TextChoices):
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"


class WatchlistSnapshot(models.Model):
    """One ingested version of an official watchlist file."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    list_slug = models.CharField(
        max_length=32,
        choices=WatchlistListSlug.choices,
        db_index=True,
    )
    source_url = models.URLField(max_length=512)
    file_sha256 = models.CharField(max_length=64, db_index=True)
    content_length = models.PositiveIntegerField(default=0)
    date_generated = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Source dateGenerated (or equivalent) from the list file.",
    )
    status = models.CharField(
        max_length=16,
        choices=WatchlistSnapshotStatus.choices,
        default=WatchlistSnapshotStatus.SUCCEEDED,
    )
    is_current = models.BooleanField(default=False, db_index=True)
    record_count = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True, default="")
    ingested_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Watchlist snapshot"
        verbose_name_plural = "Watchlist snapshots"
        ordering = ["-ingested_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["list_slug"],
                condition=models.Q(is_current=True),
                name="unique_current_watchlist_snapshot_per_list",
            ),
        ]
        indexes = [
            models.Index(fields=["list_slug", "-ingested_at"]),
        ]

    def __str__(self):
        current = "current" if self.is_current else "historic"
        return f"WatchlistSnapshot<{self.list_slug} {self.file_sha256[:12]} {current}>"


class WatchlistRecord(models.Model):
    """One designated individual or entity from a watchlist snapshot."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    snapshot = models.ForeignKey(
        WatchlistSnapshot,
        on_delete=models.CASCADE,
        related_name="records",
    )
    record_type = models.CharField(
        max_length=16,
        choices=WatchlistRecordType.choices,
        db_index=True,
    )
    reference_number = models.CharField(max_length=64, db_index=True)
    data_id = models.CharField(max_length=32, blank=True, default="")
    primary_name = models.CharField(max_length=512, blank=True, default="")
    listed_on = models.CharField(max_length=32, blank=True, default="")
    names = models.JSONField(default=list, blank=True)
    dates_of_birth = models.JSONField(default=list, blank=True)
    document_numbers = models.JSONField(default=list, blank=True)
    nationalities = models.JSONField(default=list, blank=True)
    search_document = models.TextField(
        blank=True,
        default="",
        help_text="Folded searchable blob of names, aliases, IDs, and notes.",
    )
    raw = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Watchlist record"
        verbose_name_plural = "Watchlist records"
        ordering = ["reference_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["snapshot", "reference_number"],
                name="unique_watchlist_record_per_snapshot_ref",
            ),
        ]
        indexes = [
            models.Index(fields=["snapshot", "record_type"]),
        ]

    def __str__(self):
        return f"WatchlistRecord<{self.reference_number} {self.primary_name}>"
