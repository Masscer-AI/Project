from __future__ import annotations

import uuid

from django.contrib.auth.models import User
from django.db import models


class OrganizationDataPolicy(models.Model):
    """Per-organization retention settings. null day fields = keep forever."""

    organization = models.OneToOneField(
        "authenticate.Organization",
        on_delete=models.CASCADE,
        related_name="data_policy",
    )
    deleted_conversation_retention_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Days after soft-delete before hard deletion. null = keep forever.",
    )
    attachment_retention_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Days to keep file attachments. null = keep forever.",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="data_policy_updates",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Organization data policy"
        verbose_name_plural = "Organization data policies"

    def __str__(self) -> str:
        return f"DataPolicy(org={self.organization_id})"


class DataPurgeLog(models.Model):
    class Category(models.TextChoices):
        DELETED_CONVERSATIONS = "deleted_conversations", "Deleted conversations"
        ATTACHMENTS = "attachments", "Attachments"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "authenticate.Organization",
        on_delete=models.CASCADE,
        related_name="data_purge_logs",
        null=True,
        blank=True,
    )
    category = models.CharField(max_length=32, choices=Category.choices)
    count = models.PositiveIntegerField(default=0)
    run_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-run_at"]

    def __str__(self) -> str:
        return f"DataPurgeLog({self.category}, count={self.count})"


class DataExportJob(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"
        DOWNLOADED = "downloaded", "Downloaded"

    class NotifyVia(models.TextChoices):
        APP = "app", "App"
        EMAIL = "email", "Email"
        BOTH = "both", "Both"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "authenticate.Organization",
        on_delete=models.CASCADE,
        related_name="data_exports",
    )
    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="data_export_jobs",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    notify_via = models.CharField(
        max_length=10,
        choices=NotifyVia.choices,
        default=NotifyVia.BOTH,
    )
    manifest = models.JSONField(default=dict)
    file = models.FileField(
        upload_to="data_exports/%Y/%m/",
        null=True,
        blank=True,
    )
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    download_count = models.PositiveIntegerField(default=0)
    downloaded_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"DataExportJob({self.id}, status={self.status})"
