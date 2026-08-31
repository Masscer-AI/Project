"""Update the compliance folio status or working notes."""

from __future__ import annotations

from pydantic import BaseModel, Field

from api.compliance.models import (
    ComplianceFolio,
    FolioEvent,
    FolioEventType,
    FolioStatus,
)


class UpdateFolioStatusParams(BaseModel):
    status: str | None = Field(
        default=None,
        description=(
            "open, awaiting_documents, in_review, needs_correction, "
            "pending_signature, cleared, rejected, or archived."
        ),
    )
    notes: str | None = Field(
        default=None,
        description="Replace the folio working summary (missing docs, next steps).",
    )


class UpdateFolioStatusResult(BaseModel):
    success: bool
    message: str
    folio_id: str | None = None
    status: str | None = None
    notes: str = ""


def _update_folio_status_impl(
    *,
    user_id: int,
    organization_id: int | None,
    status: str | None,
    notes: str | None,
) -> UpdateFolioStatusResult:
    qs = ComplianceFolio.objects.filter(subject_user_id=user_id)
    if organization_id is not None:
        qs = qs.filter(organization_id=organization_id)
    folio = qs.first()
    if folio is None:
        raise ValueError("No compliance folio exists yet for this user")

    changes: dict[str, str] = {}
    event_type = FolioEventType.NOTES_UPDATED
    if status is not None:
        allowed = {choice for choice, _ in FolioStatus.choices}
        if status not in allowed:
            raise ValueError(
                f"Invalid folio status '{status}'. Allowed: {', '.join(sorted(allowed))}"
            )
        if status != folio.status:
            changes["status"] = status
            folio.status = status
            event_type = FolioEventType.FOLIO_STATUS_CHANGED
    if notes is not None and notes != folio.notes:
        changes["notes"] = notes
        folio.notes = notes

    if changes:
        folio.save(update_fields=[*changes.keys(), "updated_at"])
        FolioEvent.objects.create(
            folio=folio,
            event_type=event_type,
            actor_id=user_id,
            payload=changes,
        )

    return UpdateFolioStatusResult(
        success=True,
        message="Folio updated." if changes else "No changes.",
        folio_id=str(folio.id),
        status=folio.status,
        notes=folio.notes or "",
    )


def get_tool(
    user_id: int | None = None,
    organization_id: int | str | None = None,
    **kwargs,
) -> dict:
    if not user_id:
        raise ValueError("update_folio_status requires user_id in tool context")
    org_id = None
    if organization_id not in (None, ""):
        try:
            org_id = int(organization_id)
        except (TypeError, ValueError):
            org_id = None

    def update_folio_status(
        status: str | None = None,
        notes: str | None = None,
    ) -> UpdateFolioStatusResult:
        return _update_folio_status_impl(
            user_id=int(user_id),
            organization_id=org_id,
            status=status,
            notes=notes,
        )

    return {
        "name": "update_folio_status",
        "description": (
            "Update the KYB expediente status and/or working notes. "
            "Statuses: open, awaiting_documents, in_review, needs_correction, "
            "pending_signature, cleared, rejected, archived."
        ),
        "parameters": UpdateFolioStatusParams,
        "function": update_folio_status,
    }
