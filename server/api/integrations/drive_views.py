"""
Google Drive file listing and import endpoints.
"""

from __future__ import annotations

import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from api.authenticate.decorators.token_required import token_required
from api.integrations.drive_import import (
    import_drive_file_to_document,
    list_drive_files_for_user,
)
from api.integrations.providers import IntegrationProviderError
from api.integrations.services import (
    get_user_organization,
    parse_owner_type,
    user_can_manage_integrations,
)
from api.rag.serializers import DocumentSerializer
from api.rag.views import _check_train_agents_permission

logger = logging.getLogger(__name__)


def _require_drive_access(request, owner_type: str):
    org = get_user_organization(request.user)
    if not user_can_manage_integrations(request.user, org):
        return JsonResponse(
            {"error": "The 'can-connect-drive-account' feature is not enabled."},
            status=403,
        )
    if owner_type == "organization" and org is None:
        return JsonResponse({"error": "User has no organization."}, status=400)
    return None


@csrf_exempt
@token_required
def google_drive_list_files(request):
    """
    GET /v1/integrations/google_drive/files/?owner=user|organization&limit=50
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        owner_type = parse_owner_type(request.GET.get("owner"))
        limit = int(request.GET.get("limit", "50"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    err = _require_drive_access(request, owner_type)
    if err:
        return err

    org = get_user_organization(request.user)
    try:
        files = list_drive_files_for_user(
            user=request.user,
            owner_type=owner_type,
            organization=org,
            limit=limit,
        )
    except IntegrationProviderError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse({"files": files, "owner_type": owner_type})


@csrf_exempt
@token_required
def google_drive_import(request):
    """
    POST /v1/integrations/google_drive/import/

    Body: { "file_id": "...", "owner": "user" | "organization" }
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        body = json.loads(request.body) if request.body else {}
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    file_id = (body.get("file_id") or "").strip()
    if not file_id:
        return JsonResponse({"error": "file_id is required"}, status=400)

    try:
        owner_type = parse_owner_type(body.get("owner"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    err = _require_drive_access(request, owner_type)
    if err:
        return err

    try:
        _check_train_agents_permission(request.user)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=403)

    org = get_user_organization(request.user)
    try:
        document, created = import_drive_file_to_document(
            user=request.user,
            file_id=file_id,
            owner_type=owner_type,
            organization=org,
        )
    except IntegrationProviderError as exc:
        logger.error("Drive import failed: %s", exc)
        return JsonResponse({"error": str(exc)}, status=400)

    serializer = DocumentSerializer(document, context={"request": request})
    return JsonResponse(
        {"document": serializer.data, "created": created},
        status=201 if created else 200,
    )
