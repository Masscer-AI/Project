"""Update a folio document's kind, status, or notes."""

from __future__ import annotations

from pydantic import BaseModel, Field

from api.compliance.models import (
    FolioDocument,
    FolioDocumentStatus,
    FolioEvent,
    FolioEventType,
)


class UpdateFolioDocumentParams(BaseModel):
    folio_document_id: str = Field(description="UUID from list_folio_documents.")
    document_kind: str | None = Field(
        default=None,
        description="Checklist type, e.g. ine, constancia_fiscal, acta_constitutiva.",
    )
    status: str | None = Field(
        default=None,
        description="uploaded, validated, rejected, expired, or superseded.",
    )
    notes: str | None = Field(
        default=None,
        description="Validation notes, missing items, or rejection reason.",
    )


class UpdateFolioDocumentResult(BaseModel):
    success: bool
    message: str
    id: str | None = None
    document_kind: str = ""
    status: str | None = None
    notes: str = ""


def _update_folio_document_impl(
    *,
    folio_document_id: str,
    user_id: int,
    organization_id: int | None,
    document_kind: str | None,
    status: str | None,
    notes: str | None,
) -> UpdateFolioDocumentResult:
    qs = FolioDocument.objects.filter(
        id=folio_document_id, folio__subject_user_id=user_id
    )
    if organization_id is not None:
        qs = qs.filter(folio__organization_id=organization_id)
    doc = qs.select_related("folio").first()
    if doc is None:
        raise ValueError(f"Folio document {folio_document_id} not found")

    changes: dict[str, str] = {}
    if document_kind is not None:
        cleaned = document_kind.strip()
        if cleaned != doc.document_kind:
            changes["document_kind"] = cleaned
            doc.document_kind = cleaned
    if status is not None:
        allowed = {choice for choice, _ in FolioDocumentStatus.choices}
        if status not in allowed:
            raise ValueError(
                f"Invalid document status '{status}'. Allowed: {', '.join(sorted(allowed))}"
            )
        if status != doc.status:
            changes["status"] = status
            doc.status = status
    if notes is not None and notes != doc.notes:
        changes["notes"] = notes
        doc.notes = notes

    if changes:
        doc.save(update_fields=[*changes.keys(), "updated_at"])
        FolioEvent.objects.create(
            folio=doc.folio,
            folio_document=doc,
            event_type=FolioEventType.DOCUMENT_UPDATED,
            actor_id=user_id,
            payload=changes,
        )

    return UpdateFolioDocumentResult(
        success=True,
        message="Folio document updated." if changes else "No changes.",
        id=str(doc.id),
        document_kind=doc.document_kind or "",
        status=doc.status,
        notes=doc.notes or "",
    )


def get_tool(
    user_id: int | None = None,
    organization_id: int | str | None = None,
    **kwargs,
) -> dict:
    if not user_id:
        raise ValueError("update_folio_document requires user_id in tool context")
    org_id = None
    if organization_id not in (None, ""):
        try:
            org_id = int(organization_id)
        except (TypeError, ValueError):
            org_id = None

    def update_folio_document(
        folio_document_id: str,
        document_kind: str | None = None,
        status: str | None = None,
        notes: str | None = None,
    ) -> UpdateFolioDocumentResult:
        return _update_folio_document_impl(
            folio_document_id=folio_document_id,
            user_id=int(user_id),
            organization_id=org_id,
            document_kind=document_kind,
            status=status,
            notes=notes,
        )

    return {
        "name": "update_folio_document",
        "description": (
            "Update a KYB folio document: classify document_kind, set status "
            "(uploaded/validated/rejected/expired/superseded), and/or notes. "
            "Use after read_attachment."
        ),
        "parameters": UpdateFolioDocumentParams,
        "function": update_folio_document,
    }
