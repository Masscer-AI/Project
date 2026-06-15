import json
import logging

from django.http import FileResponse, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from api.authenticate.decorators.token_required import token_required
from api.authenticate.models import Organization
from api.data_governance.models import DataExportJob, OrganizationDataPolicy
from api.data_governance.permissions import can_manage_data_governance
from api.data_governance.schemas import parse_export_manifest, parse_policy_patch
from api.data_governance.serializers import serialize_export_job, serialize_policy
from api.data_governance.tasks import run_data_export_job

logger = logging.getLogger(__name__)


def _get_org_or_404(organization_id):
    try:
        return Organization.objects.get(id=organization_id)
    except Organization.DoesNotExist:
        return None


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class OrganizationDataPolicyView(View):
    def get(self, request, organization_id):
        org = _get_org_or_404(organization_id)
        if not org:
            return JsonResponse({"error": "Organization not found"}, status=404)
        if not can_manage_data_governance(request.user, org):
            return JsonResponse({"error": "Forbidden"}, status=403)

        policy, _ = OrganizationDataPolicy.objects.get_or_create(organization=org)
        return JsonResponse(serialize_policy(policy))

    def patch(self, request, organization_id):
        org = _get_org_or_404(organization_id)
        if not org:
            return JsonResponse({"error": "Organization not found"}, status=404)
        if not can_manage_data_governance(request.user, org):
            return JsonResponse({"error": "Forbidden"}, status=403)

        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        try:
            parsed = parse_policy_patch(body)
        except Exception as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        policy, _ = OrganizationDataPolicy.objects.get_or_create(organization=org)
        policy.deleted_conversation_retention_days = parsed.deleted_conversation_retention_days
        policy.attachment_retention_days = parsed.attachment_retention_days
        policy.updated_by = request.user
        policy.save(
            update_fields=[
                "deleted_conversation_retention_days",
                "attachment_retention_days",
                "updated_by",
                "updated_at",
            ]
        )
        return JsonResponse(serialize_policy(policy))


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class DataExportJobListCreateView(View):
    def get(self, request, organization_id):
        org = _get_org_or_404(organization_id)
        if not org:
            return JsonResponse({"error": "Organization not found"}, status=404)
        if not can_manage_data_governance(request.user, org):
            return JsonResponse({"error": "Forbidden"}, status=403)

        jobs = DataExportJob.objects.filter(organization=org).order_by("-created_at")[:50]
        return JsonResponse(
            [serialize_export_job(j) for j in jobs],
            safe=False,
        )

    def post(self, request, organization_id):
        org = _get_org_or_404(organization_id)
        if not org:
            return JsonResponse({"error": "Organization not found"}, status=404)
        if not can_manage_data_governance(request.user, org):
            return JsonResponse({"error": "Forbidden"}, status=403)

        active = DataExportJob.objects.filter(
            organization=org,
            status__in=[
                DataExportJob.Status.PENDING,
                DataExportJob.Status.PROCESSING,
            ],
        ).exists()
        if active:
            return JsonResponse(
                {"error": "An export is already in progress for this organization"},
                status=409,
            )

        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        manifest_raw = body.get("manifest") or body
        notify_via = (body.get("notify_via") or "both").lower()
        if notify_via not in {c.value for c in DataExportJob.NotifyVia}:
            return JsonResponse({"error": "Invalid notify_via"}, status=400)

        if isinstance(manifest_raw.get("date_from"), str):
            manifest_raw = dict(manifest_raw)
            manifest_raw["date_from"] = parse_date(manifest_raw["date_from"])
            manifest_raw["date_to"] = parse_date(manifest_raw["date_to"])

        try:
            manifest = parse_export_manifest(manifest_raw)
        except Exception as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        job = DataExportJob.objects.create(
            organization=org,
            requested_by=request.user,
            notify_via=notify_via,
            manifest=manifest.model_dump(mode="json"),
            status=DataExportJob.Status.PENDING,
        )
        run_data_export_job.delay(str(job.id))
        return JsonResponse(serialize_export_job(job), status=202)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class DataExportJobDetailView(View):
    def get(self, request, organization_id, job_id):
        org = _get_org_or_404(organization_id)
        if not org:
            return JsonResponse({"error": "Organization not found"}, status=404)
        if not can_manage_data_governance(request.user, org):
            return JsonResponse({"error": "Forbidden"}, status=403)

        try:
            job = DataExportJob.objects.get(id=job_id, organization=org)
        except DataExportJob.DoesNotExist:
            return JsonResponse({"error": "Export job not found"}, status=404)

        return JsonResponse(serialize_export_job(job))


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class DataExportJobDownloadView(View):
    def get(self, request, organization_id, job_id):
        org = _get_org_or_404(organization_id)
        if not org:
            return JsonResponse({"error": "Organization not found"}, status=404)
        if not can_manage_data_governance(request.user, org):
            return JsonResponse({"error": "Forbidden"}, status=403)

        try:
            job = DataExportJob.objects.get(id=job_id, organization=org)
        except DataExportJob.DoesNotExist:
            return JsonResponse({"error": "Export job not found"}, status=404)

        if job.status != DataExportJob.Status.READY:
            return JsonResponse(
                {"error": f"Export is not ready (status={job.status})"},
                status=400,
            )
        if job.expires_at and job.expires_at < timezone.now():
            return JsonResponse({"error": "Export has expired"}, status=410)
        if not job.file:
            return JsonResponse({"error": "Export file not available"}, status=404)

        from api.data_governance.tasks import finalize_download

        try:
            file_handle = job.file.open("rb")
        except Exception:
            return JsonResponse({"error": "Could not open export file"}, status=500)

        filename = f"masscer-export-{job.id}.zip"
        response = FileResponse(file_handle, as_attachment=True, filename=filename)
        response["Content-Type"] = "application/zip"

        job_id_str = str(job.id)
        original_close = response.close

        def _close_and_finalize():
            original_close()
            from api.data_governance.models import DataExportJob as JobModel
            from api.data_governance.tasks import finalize_download

            try:
                refreshed = JobModel.objects.get(id=job_id_str)
                finalize_download(refreshed)
            except JobModel.DoesNotExist:
                pass

        response.close = _close_and_finalize
        return response
