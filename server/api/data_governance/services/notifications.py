from __future__ import annotations

import logging
from html import escape

from django.conf import settings

from api.data_governance.models import DataExportJob
from api.notify.actions import notify_user
from api.utils.email_service import EmailService

logger = logging.getLogger(__name__)


def _frontend_export_url(job: DataExportJob) -> str:
    base = getattr(settings, "FRONTEND_URL", "").rstrip("/")
    if not base:
        base = ""
    return f"{base}/organization?activeTab=data&export={job.id}"


def _send_export_ready_email(job: DataExportJob) -> None:
    user = job.requested_by
    if not user or not (user.email or "").strip():
        return
    try:
        service = EmailService()
    except ValueError:
        logger.warning("Skipping export email: RESEND_API_KEY not configured")
        return

    export_url = _frontend_export_url(job)
    size_mb = ""
    if job.file_size_bytes:
        size_mb = f" ({job.file_size_bytes / (1024 * 1024):.1f} MB)"

    link_html = ""
    if export_url.startswith("http"):
        safe_href = escape(export_url)
        link_html = (
            f'<p style="margin-top:18px;">'
            f'<a href="{safe_href}" style="color:#6d28d9;font-weight:600;">'
            "Download your export"
            "</a></p>"
        )
    else:
        link_html = (
            "<p>Open the Data Governance section in your organization settings "
            "to download your export.</p>"
        )

    html = (
        f"<p>Your organization data export is ready{escape(size_mb)}.</p>"
        f"{link_html}"
        f'<p style="color:#666;font-size:12px;">'
        f"Export ID: {escape(str(job.id))}</p>"
    )
    subject = "Masscer: Your data export is ready"
    try:
        service.send_email(to=user.email, html=html, subject=subject, from_name="Masscer")
    except Exception:
        logger.exception("Export ready email failed for job %s", job.id)


def notify_export_ready(job: DataExportJob) -> None:
    notify_via = job.notify_via
    payload = {
        "job_id": str(job.id),
        "organization_id": str(job.organization_id),
        "file_size_bytes": job.file_size_bytes,
        "status": job.status,
    }

    if notify_via in (DataExportJob.NotifyVia.APP, DataExportJob.NotifyVia.BOTH):
        if job.requested_by_id:
            notify_user(job.requested_by_id, "data_export_ready", payload)

    if notify_via in (DataExportJob.NotifyVia.EMAIL, DataExportJob.NotifyVia.BOTH):
        _send_export_ready_email(job)
