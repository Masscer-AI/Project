from api.data_governance.models import DataExportJob, OrganizationDataPolicy


def serialize_policy(policy: OrganizationDataPolicy) -> dict:
    return {
        "deleted_conversation_retention_days": policy.deleted_conversation_retention_days,
        "attachment_retention_days": policy.attachment_retention_days,
        "updated_at": policy.updated_at.isoformat() if policy.updated_at else None,
        "updated_by_id": policy.updated_by_id,
    }


def serialize_export_job(job: DataExportJob) -> dict:
    return {
        "id": str(job.id),
        "organization_id": str(job.organization_id),
        "requested_by_id": job.requested_by_id,
        "status": job.status,
        "notify_via": job.notify_via,
        "manifest": job.manifest,
        "file_size_bytes": job.file_size_bytes,
        "download_count": job.download_count,
        "downloaded_at": job.downloaded_at.isoformat() if job.downloaded_at else None,
        "expires_at": job.expires_at.isoformat() if job.expires_at else None,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
