from __future__ import annotations

import json
import uuid

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from api.authenticate.decorators.token_required import token_required
from api.authenticate.models import Organization
from api.org_lists.access import user_can_manage_org_lists
from api.org_lists.models import OrganizationList, OrganizationListRecord
from api.org_lists.tasks import process_organization_list_import
from api.utils.error_response import error_response


def _list_to_dict(org_list: OrganizationList, *, include_config: bool = True) -> dict:
    payload = {
        "id": str(org_list.id),
        "organization_id": str(org_list.organization_id),
        "name": org_list.name,
        "description": org_list.description or "",
        "import_status": org_list.import_status,
        "import_error": org_list.import_error or "",
        "record_count": org_list.record_count,
        "original_filename": org_list.original_filename or "",
        "content_type": org_list.content_type or "",
        "file_size": org_list.file_size,
        "created_at": org_list.created_at.isoformat() if org_list.created_at else None,
        "updated_at": org_list.updated_at.isoformat() if org_list.updated_at else None,
    }
    if include_config:
        payload["config"] = org_list.config or {}
    return payload


def _record_to_dict(record: OrganizationListRecord) -> dict:
    return {
        "id": str(record.id),
        "position": record.position,
        "data": record.data or {},
    }


def _get_org_or_403(request, org_id: str) -> Organization | JsonResponse:
    try:
        org = Organization.objects.get(id=org_id)
    except (Organization.DoesNotExist, ValueError):
        return JsonResponse({"error": "Organization not found"}, status=404)
    if not user_can_manage_org_lists(request.user, org):
        return JsonResponse({"error": "Forbidden"}, status=403)
    return org


def _get_list_or_404(org: Organization, list_id: str) -> OrganizationList | JsonResponse:
    org_list = OrganizationList.objects.filter(organization=org, id=list_id).first()
    if not org_list:
        return JsonResponse({"error": "List not found"}, status=404)
    return org_list


def _save_upload_file(org_list: OrganizationList, uploaded) -> None:
    name = uploaded.name or "list.csv"
    org_list.original_filename = name
    org_list.file_size = getattr(uploaded, "size", 0) or 0
    org_list.content_type = getattr(uploaded, "content_type", "") or org_list.content_type
    ext = name[name.rfind(".") :] if "." in name else ".csv"
    org_list.file.save(f"{uuid.uuid4()}{ext}", uploaded, save=False)


def _enqueue_import(org_list: OrganizationList) -> None:
    org_list.import_status = OrganizationList.ImportStatus.PENDING
    org_list.import_error = ""
    org_list.save(update_fields=["import_status", "import_error", "updated_at"])
    process_organization_list_import.delay(str(org_list.id))


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class OrganizationListCollectionView(View):
    def get(self, request, org_id: str):
        org = _get_org_or_403(request, org_id)
        if isinstance(org, JsonResponse):
            return org
        qs = OrganizationList.objects.filter(organization=org).order_by("-created_at")
        return JsonResponse({"lists": [_list_to_dict(row, include_config=False) for row in qs]})

    def post(self, request, org_id: str):
        org = _get_org_or_403(request, org_id)
        if isinstance(org, JsonResponse):
            return org
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        uploaded = request.FILES.get("file")
        if not name:
            return JsonResponse({"error": "name is required"}, status=400)
        if not uploaded:
            return JsonResponse({"error": "file is required"}, status=400)
        org_list = OrganizationList(
            organization=org,
            name=name,
            description=description,
            uploaded_by=request.user,
        )
        try:
            _save_upload_file(org_list, uploaded)
            org_list.save()
            _enqueue_import(org_list)
        except Exception as exc:
            return error_response(exc)
        return JsonResponse({"list": _list_to_dict(org_list)}, status=202)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class OrganizationListDetailView(View):
    def get(self, request, org_id: str, list_id: str):
        org = _get_org_or_403(request, org_id)
        if isinstance(org, JsonResponse):
            return org
        org_list = _get_list_or_404(org, list_id)
        if isinstance(org_list, JsonResponse):
            return org_list
        return JsonResponse({"list": _list_to_dict(org_list)})

    def patch(self, request, org_id: str, list_id: str):
        org = _get_org_or_403(request, org_id)
        if isinstance(org, JsonResponse):
            return org
        org_list = _get_list_or_404(org, list_id)
        if isinstance(org_list, JsonResponse):
            return org_list
        try:
            body = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        if "name" in body:
            name = str(body.get("name") or "").strip()
            if name:
                org_list.name = name
        if "description" in body:
            org_list.description = str(body.get("description") or "")
        org_list.save()
        return JsonResponse({"list": _list_to_dict(org_list)})

    def delete(self, request, org_id: str, list_id: str):
        org = _get_org_or_403(request, org_id)
        if isinstance(org, JsonResponse):
            return org
        org_list = _get_list_or_404(org, list_id)
        if isinstance(org_list, JsonResponse):
            return org_list
        if org_list.file:
            org_list.file.delete(save=False)
        org_list.delete()
        return JsonResponse({"ok": True})


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class OrganizationListFileView(View):
    def post(self, request, org_id: str, list_id: str):
        org = _get_org_or_403(request, org_id)
        if isinstance(org, JsonResponse):
            return org
        org_list = _get_list_or_404(org, list_id)
        if isinstance(org_list, JsonResponse):
            return org_list
        uploaded = request.FILES.get("file")
        if not uploaded:
            return JsonResponse({"error": "file is required"}, status=400)
        try:
            if org_list.file:
                org_list.file.delete(save=False)
            _save_upload_file(org_list, uploaded)
            org_list.save()
            _enqueue_import(org_list)
        except Exception as exc:
            return error_response(exc)
        org_list.refresh_from_db()
        return JsonResponse({"list": _list_to_dict(org_list)}, status=202)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class OrganizationListRecordsView(View):
    def get(self, request, org_id: str, list_id: str):
        org = _get_org_or_403(request, org_id)
        if isinstance(org, JsonResponse):
            return org
        org_list = _get_list_or_404(org, list_id)
        if isinstance(org_list, JsonResponse):
            return org_list
        try:
            page = max(1, int(request.GET.get("page", "1")))
        except ValueError:
            page = 1
        try:
            page_size = min(200, max(1, int(request.GET.get("page_size", "50"))))
        except ValueError:
            page_size = 50
        qs = OrganizationListRecord.objects.filter(organization_list=org_list).order_by(
            "position"
        )
        total = qs.count()
        start = (page - 1) * page_size
        records = list(qs[start : start + page_size])
        return JsonResponse(
            {
                "page": page,
                "page_size": page_size,
                "total": total,
                "records": [_record_to_dict(r) for r in records],
            }
        )
