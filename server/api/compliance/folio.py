"""Create and update compliance folios from chat uploads."""

from __future__ import annotations

from django.db import transaction

from api.compliance.models import (
    ComplianceFolio,
    FolioDocument,
    FolioDocumentStatus,
    FolioEvent,
    FolioEventType,
    FolioStatus,
)
from api.messaging.schemas import ConversationMetadata


def conversation_is_compliance(conversation) -> bool:
    meta = getattr(conversation, "metadata", None)
    return isinstance(meta, dict) and meta.get("surface") == "compliance"


def is_compliance_evidence(attachment) -> bool:
    if attachment is None:
        return False
    if FolioDocument.objects.filter(attachment_id=attachment.id).exists():
        return True
    metadata = getattr(attachment, "metadata", None)
    if isinstance(metadata, dict) and metadata.get("compliance") is True:
        return True
    return conversation_is_compliance(getattr(attachment, "conversation", None))


def get_or_create_folio(organization, subject_user) -> tuple[ComplianceFolio, bool]:
    folio, created = ComplianceFolio.objects.get_or_create(
        organization=organization,
        subject_user=subject_user,
        defaults={"status": FolioStatus.OPEN},
    )
    if created:
        FolioEvent.objects.create(
            folio=folio,
            event_type=FolioEventType.FOLIO_CREATED,
            actor=subject_user,
            payload={"status": folio.status},
        )
    return folio, created


def _set_conversation_folio_id(conversation, folio: ComplianceFolio) -> None:
    meta = conversation.metadata if isinstance(conversation.metadata, dict) else {}
    if meta.get("folio_id") == str(folio.id):
        return
    parsed = ConversationMetadata.model_validate({**meta, "folio_id": str(folio.id)})
    conversation.metadata = parsed.model_dump(mode="json", exclude_none=True)
    conversation.save(update_fields=["metadata", "updated_at"])


def ingest_compliance_attachment(attachment, *, actor=None) -> FolioDocument | None:
    """
    If this file was uploaded on a compliance conversation, attach it to the
    subject's folio. No-op for other chats or attachments already linked.
    """
    conversation = getattr(attachment, "conversation", None)
    if conversation is None or not conversation_is_compliance(conversation):
        return None
    if getattr(attachment, "kind", "file") != "file":
        return None
    if not getattr(attachment, "file", None):
        return None

    organization = getattr(conversation, "organization", None)
    subject_user = getattr(conversation, "user", None) or getattr(attachment, "user", None)
    if organization is None or subject_user is None:
        return None

    with transaction.atomic():
        existing = FolioDocument.objects.filter(attachment=attachment).first()
        if existing:
            return existing

        folio, _ = get_or_create_folio(organization, subject_user)
        _set_conversation_folio_id(conversation, folio)

        metadata = attachment.metadata if isinstance(attachment.metadata, dict) else {}
        metadata = {**metadata, "compliance": True}
        attachment.metadata = metadata
        attachment.expires_at = None
        attachment.save(update_fields=["metadata", "expires_at"])

        document = FolioDocument.objects.create(
            folio=folio,
            attachment=attachment,
            status=FolioDocumentStatus.UPLOADED,
        )
        FolioEvent.objects.create(
            folio=folio,
            folio_document=document,
            event_type=FolioEventType.DOCUMENT_UPLOADED,
            actor=actor or getattr(attachment, "user", None),
            payload={"attachment_id": str(attachment.id)},
        )
        return document


def folio_runtime_lines(folio: ComplianceFolio | None) -> list[str]:
    if folio is None:
        return []
    lines = [
        f"Folio id: {folio.id}",
        f"Folio status: {folio.status}",
    ]
    if (folio.notes or "").strip():
        lines.append(f"Folio notes: {folio.notes.strip()}")
    documents = list(folio.documents.select_related("attachment").order_by("created_at"))
    if not documents:
        lines.append("Folio documents: none")
        return lines
    lines.append("Folio documents:")
    for doc in documents:
        att = doc.attachment
        name = ""
        if att and att.file and getattr(att.file, "name", None):
            name = att.file.name.split("/")[-1]
        kind = doc.document_kind or "unspecified"
        att_id = str(att.id) if att else ""
        lines.append(
            f"- id={doc.id} kind={kind} status={doc.status} "
            f"attachment_id={att_id} name={name}"
        )
        if (doc.notes or "").strip():
            lines.append(f"  notes: {doc.notes.strip()}")
    return lines
