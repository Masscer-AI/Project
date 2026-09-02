from __future__ import annotations

import json

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from api.authenticate.decorators.token_required import token_required
from api.compliance.access import get_pld_organization_for_user
from api.compliance.models import (
    PLDEntity,
    PLDExpedient,
    PLDExpedientStatus,
    PLDPersonType,
    PLDRelationship,
)


def _entity_payload(entity: PLDEntity) -> dict:
    expedient = entity.expedients.order_by("created_at").first()
    return {
        "id": str(entity.id),
        "person_type": entity.person_type,
        "relationship": entity.relationship,
        "metadata": entity.metadata or {},
        "created_at": entity.created_at.isoformat() if entity.created_at else None,
        "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
        "expedient": (
            {
                "id": str(expedient.id),
                "status": expedient.status,
                "vulnerable_activity": expedient.vulnerable_activity,
            }
            if expedient
            else None
        ),
    }


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class PLDEntityListView(View):
    """List and create PLD counterparties for the user's PLD-enabled organization."""

    def get(self, request, *args, **kwargs):
        org = get_pld_organization_for_user(request.user)
        if org is None:
            return JsonResponse(
                {"error": "PLD is not enabled for this organization"},
                status=404,
            )
        entities = (
            PLDEntity.objects.filter(organization=org)
            .prefetch_related("expedients")
            .order_by("-updated_at")
        )
        return JsonResponse(
            {"results": [_entity_payload(entity) for entity in entities]},
            status=200,
        )

    def post(self, request, *args, **kwargs):
        org = get_pld_organization_for_user(request.user)
        if org is None:
            return JsonResponse(
                {"error": "PLD is not enabled for this organization"},
                status=404,
            )
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)
        if not isinstance(payload, dict):
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        person_type = payload.get("person_type")
        relationship = payload.get("relationship")
        metadata = payload.get("metadata") or {}
        if person_type not in PLDPersonType.values:
            return JsonResponse({"error": "Invalid person_type"}, status=400)
        if relationship not in PLDRelationship.values:
            return JsonResponse(
                {"error": "relationship is required (cliente, proveedor, or ambos)"},
                status=400,
            )
        if not isinstance(metadata, dict):
            return JsonResponse({"error": "metadata must be an object"}, status=400)

        try:
            with transaction.atomic():
                entity = PLDEntity(
                    organization=org,
                    person_type=person_type,
                    relationship=relationship,
                    metadata=metadata,
                )
                entity.save()
                PLDExpedient.objects.get_or_create(
                    organization=org,
                    entity=entity,
                    defaults={"status": PLDExpedientStatus.DATA_COLLECTION},
                )
        except ValidationError as exc:
            return JsonResponse(
                {"error": getattr(exc, "message_dict", None) or str(exc)},
                status=400,
            )

        entity = PLDEntity.objects.prefetch_related("expedients").get(pk=entity.pk)
        return JsonResponse(_entity_payload(entity), status=201)
