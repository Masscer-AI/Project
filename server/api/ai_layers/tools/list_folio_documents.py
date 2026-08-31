"""List documents on the current user's compliance folio."""

from __future__ import annotations

from pydantic import BaseModel, Field

from api.compliance.models import ComplianceFolio, FolioDocument


class ListFolioDocumentsParams(BaseModel):
    pass


class FolioDocumentItem(BaseModel):
    id: str
    attachment_id: str
    document_kind: str
    status: str
    notes: str
    name: str | None = None
    content_type: str = ""
    created_at: str | None = None


class ListFolioDocumentsResult(BaseModel):
    folio_id: str | None = None
    folio_status: str | None = None
    folio_notes: str = ""
    documents: list[FolioDocumentItem] = Field(default_factory=list)
    message: str = ""


def _document_name(doc: FolioDocument) -> str | None:
    att = doc.attachment
    if att and att.file and getattr(att.file, "name", None):
        return att.file.name.split("/")[-1]
    return None


def _list_folio_documents_impl(
    *, user_id: int, organization_id: int | None
) -> ListFolioDocumentsResult:
    qs = ComplianceFolio.objects.filter(subject_user_id=user_id)
    if organization_id is not None:
        qs = qs.filter(organization_id=organization_id)
    folio = qs.prefetch_related("documents__attachment").first()
    if folio is None:
        return ListFolioDocumentsResult(
            message="No compliance folio exists yet for this user.",
        )
    items = [
        FolioDocumentItem(
            id=str(doc.id),
            attachment_id=str(doc.attachment_id),
            document_kind=doc.document_kind or "",
            status=doc.status,
            notes=doc.notes or "",
            name=_document_name(doc),
            content_type=getattr(doc.attachment, "content_type", "") or "",
            created_at=doc.created_at.isoformat() if doc.created_at else None,
        )
        for doc in folio.documents.all()
    ]
    return ListFolioDocumentsResult(
        folio_id=str(folio.id),
        folio_status=folio.status,
        folio_notes=folio.notes or "",
        documents=items,
        message=f"Listed {len(items)} folio document(s).",
    )


def get_tool(
    user_id: int | None = None,
    organization_id: int | str | None = None,
    **kwargs,
) -> dict:
    if not user_id:
        raise ValueError("list_folio_documents requires user_id in tool context")
    org_id = None
    if organization_id not in (None, ""):
        try:
            org_id = int(organization_id)
        except (TypeError, ValueError):
            org_id = None

    def list_folio_documents() -> ListFolioDocumentsResult:
        return _list_folio_documents_impl(user_id=int(user_id), organization_id=org_id)

    return {
        "name": "list_folio_documents",
        "description": (
            "List KYB expediente documents for the current user: id, attachment_id, "
            "kind, status, and notes. Use read_attachment to inspect a file. "
            "Use update_folio_document to classify or validate a document."
        ),
        "parameters": ListFolioDocumentsParams,
        "function": list_folio_documents,
    }
