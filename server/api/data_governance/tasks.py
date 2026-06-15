from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from api.data_governance.constants import EXPORT_MAX_DOWNLOAD_COUNT
from api.data_governance.models import DataExportJob
from api.data_governance.services.export_runner import run_export_job
from api.data_governance.services.retention import run_retention_purge

logger = logging.getLogger(__name__)


@shared_task(name="api.data_governance.tasks.purge_expired_data")
def purge_expired_data():
    totals = run_retention_purge()
    logger.info("Data retention purge completed: %s", totals)
    return totals


@shared_task(name="api.data_governance.tasks.run_data_export_job")
def run_data_export_job(job_id: str):
    run_export_job(job_id)


@shared_task(name="api.data_governance.tasks.expire_stale_data_exports")
def expire_stale_data_exports():
    now = timezone.now()
    qs = DataExportJob.objects.filter(
        status=DataExportJob.Status.READY,
        expires_at__lt=now,
    )
    expired = 0
    for job in qs.iterator():
        if job.file:
            try:
                job.file.delete(save=False)
            except Exception:
                logger.exception("Failed to delete export file for job %s", job.id)
        job.status = DataExportJob.Status.EXPIRED
        job.save(update_fields=["status"])
        expired += 1
    logger.info("Expired %s stale data export jobs", expired)
    return {"expired": expired}


def finalize_download(job: DataExportJob) -> None:
    """Increment download count; delete file after max downloads."""
    job.download_count += 1
    job.downloaded_at = timezone.now()
    update_fields = ["download_count", "downloaded_at"]

    if job.download_count >= EXPORT_MAX_DOWNLOAD_COUNT:
        if job.file:
            try:
                job.file.delete(save=False)
            except Exception:
                logger.exception("Failed to delete export file after download %s", job.id)
            job.file = None
            update_fields.append("file")
        job.status = DataExportJob.Status.DOWNLOADED
        update_fields.append("status")

    job.save(update_fields=update_fields)
