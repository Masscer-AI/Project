from __future__ import annotations

import json
import logging
import shutil
import tempfile
import zipfile
from pathlib import Path

from django.core.files.base import ContentFile
from django.utils import timezone

from api.data_governance.constants import EXPORT_FILE_TTL_DAYS
from api.data_governance.exporters import EXPORTERS
from api.data_governance.models import DataExportJob
from api.data_governance.schemas import parse_export_manifest
from api.data_governance.services.notifications import notify_export_ready

logger = logging.getLogger(__name__)


def _build_readme() -> str:
    return (
        "Masscer Data Export\n"
        "===================\n\n"
        "This archive contains organization data exported per your request.\n"
        "See export_manifest.json for details on included categories.\n"
    )


def run_export_job(job_id: str) -> None:
    job = DataExportJob.objects.select_related("organization", "requested_by").get(
        id=job_id
    )
    if job.status not in (DataExportJob.Status.PENDING, DataExportJob.Status.PROCESSING):
        return

    job.status = DataExportJob.Status.PROCESSING
    job.error_message = ""
    job.save(update_fields=["status", "error_message"])

    tmpdir = tempfile.mkdtemp(prefix="masscer_export_")
    try:
        manifest = parse_export_manifest(job.manifest)
        org = job.organization
        output_dir = Path(tmpdir)
        all_artifacts = []
        summary: dict = {}

        for key, exporter in EXPORTERS.items():
            result = exporter.export(
                organization=org,
                manifest=manifest,
                output_dir=output_dir,
            )
            all_artifacts.extend(result.artifacts)
            summary.update(result.summary)

        manifest_payload = {
            "job_id": str(job.id),
            "organization_id": str(org.id),
            "exported_at": timezone.now().isoformat(),
            "manifest": job.manifest,
            "summary": summary,
            "files": [a.relative_path for a in all_artifacts],
        }
        (output_dir / "export_manifest.json").write_text(
            json.dumps(manifest_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (output_dir / "README.txt").write_text(_build_readme(), encoding="utf-8")

        zip_path = output_dir / f"export-{job.id}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in output_dir.rglob("*"):
                if path.is_file() and path != zip_path:
                    zf.write(path, arcname=path.relative_to(output_dir).as_posix())

        zip_bytes = zip_path.read_bytes()
        filename = f"export-{job.id}.zip"
        job.file.save(filename, ContentFile(zip_bytes), save=False)
        job.file_size_bytes = len(zip_bytes)
        job.status = DataExportJob.Status.READY
        job.completed_at = timezone.now()
        job.expires_at = job.completed_at + timezone.timedelta(days=EXPORT_FILE_TTL_DAYS)
        job.save(
            update_fields=[
                "file",
                "file_size_bytes",
                "status",
                "completed_at",
                "expires_at",
            ]
        )

        notify_export_ready(job)
    except Exception as exc:
        logger.exception("Data export job %s failed", job_id)
        job.status = DataExportJob.Status.FAILED
        job.error_message = str(exc)[:2000]
        job.save(update_fields=["status", "error_message"])
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
