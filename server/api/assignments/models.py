from __future__ import annotations

import uuid

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models

from api.assignments.schemas import validate_assignment_metadata


class AssignmentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    IN_PROGRESS = "in_progress", "In progress"
    DONE = "done", "Done"
    ARCHIVED = "archived", "Archived"


class UserAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="assignments"
    )
    organization = models.ForeignKey(
        "authenticate.Organization",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="user_assignments",
    )
    key = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    title = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=AssignmentStatus.choices,
        default=AssignmentStatus.PENDING,
        db_index=True,
    )
    metadata = models.JSONField(default=dict, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "key"],
                condition=models.Q(key__isnull=False),
                name="unique_user_assignment_key",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"UserAssignment({self.id}, {self.title!r}, {self.status})"

    def clean(self) -> None:
        super().clean()
        if not self.metadata:
            raise ValidationError({"metadata": "metadata must not be empty"})
        try:
            validate_assignment_metadata(self.metadata)
        except Exception as exc:
            raise ValidationError({"metadata": str(exc)}) from exc

    def save(self, *args, **kwargs):
        if self.metadata:
            meta = validate_assignment_metadata(self.metadata)
            self.metadata = meta.model_dump(mode="json")
        self.full_clean()
        super().save(*args, **kwargs)

    def parsed_metadata(self):
        return validate_assignment_metadata(self.metadata)
