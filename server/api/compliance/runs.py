from __future__ import annotations

from django.db import transaction

from api.compliance.models import (
    PLD_CLOSED_STATUSES,
    PLDEntity,
    PLDExpedient,
    PLDExpedientStatus,
)

_PER_RUN_ANSWERS = {
    "truthfulness_accepted": False,
    "declares_pep": None,
    "partners_pep": None,
    "partners_pep_names": None,
    "third_party_payments": None,
    "foreign_operations": None,
    "foreign_countries": None,
    "notice_invoices_done": False,
}


def score_run_matrix(entity: PLDEntity, exp: PLDExpedient) -> dict | None:
    from api.compliance.risk.matrix_score import score_pld_matrix

    if exp.screening_status != PLDExpedient.PrequalificationStatus.SUCCEEDED:
        return None
    try:
        return score_pld_matrix(entity, exp)
    except Exception:
        return None


def freeze_expedient(exp: PLDExpedient) -> None:
    entity = exp.entity
    exp.entity_snapshot = {
        "metadata": entity.metadata if isinstance(entity.metadata, dict) else {},
        "matrix": score_run_matrix(entity, exp),
        "matrix_profile": entity.matrix_profile.name if entity.matrix_profile else "",
    }


def start_new_run(entity: PLDEntity) -> PLDExpedient:
    with transaction.atomic():
        entity = (
            PLDEntity.objects.select_for_update()
            .select_related("organization", "matrix_profile")
            .get(pk=entity.pk)
        )
        latest = entity.current_expedient()
        if latest and latest.status not in PLD_CLOSED_STATUSES:
            raise ValueError("expedient-open")
        if latest and not latest.entity_snapshot:
            latest.completed_at = latest.completed_at or latest.updated_at
            freeze_expedient(latest)
            latest.save(update_fields=["completed_at", "entity_snapshot", "updated_at"])
        if entity.metadata:
            entity.metadata = {**entity.metadata, **_PER_RUN_ANSWERS}
            entity.save(update_fields=["metadata", "updated_at"])
        return PLDExpedient.objects.create(
            organization=entity.organization,
            entity=entity,
            version=latest.version + 1 if latest else 1,
            status=PLDExpedientStatus.DATA_COLLECTION,
        )
