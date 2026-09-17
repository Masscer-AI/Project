from __future__ import annotations

import os
import uuid

from django.contrib.auth.models import User
from django.db import models

from api.org_lists.schemas import default_config_dict


def organization_list_upload_to(instance: "OrganizationList", filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower() or ".csv"
    return f"org_lists/org_{instance.organization_id}/{uuid.uuid4()}{ext}"


class OrganizationList(models.Model):
    class ImportStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "authenticate.Organization",
        on_delete=models.CASCADE,
        related_name="organization_lists",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    file = models.FileField(upload_to=organization_list_upload_to)
    original_filename = models.CharField(max_length=255, blank=True, default="")
    content_type = models.CharField(max_length=128, blank=True, default="")
    file_size = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organization_lists_uploaded",
    )
    config = models.JSONField(default=default_config_dict, blank=True)
    import_status = models.CharField(
        max_length=16,
        choices=ImportStatus.choices,
        default=ImportStatus.PENDING,
        db_index=True,
    )
    import_error = models.TextField(blank=True, default="")
    record_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"OrganizationList({self.name}, org={self.organization_id})"


class OrganizationListRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization_list = models.ForeignKey(
        OrganizationList,
        on_delete=models.CASCADE,
        related_name="records",
    )
    position = models.PositiveIntegerField()
    data = models.JSONField(default=dict, blank=True)
    search_document = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization_list", "position"],
                name="unique_org_list_record_position",
            ),
        ]

    def __str__(self) -> str:
        return f"OrganizationListRecord(list={self.organization_list_id}, pos={self.position})"
