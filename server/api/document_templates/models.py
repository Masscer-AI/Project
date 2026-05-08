from __future__ import annotations

import os
import uuid

from django.contrib.auth.models import User
from django.db import models


def document_template_upload_to(instance: "DocumentTemplate", filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower() or ".docx"
    return f"document_templates/org_{instance.organization_id}/{uuid.uuid4()}{ext}"


class DocumentTemplate(models.Model):
    """
    Organization-owned Word template with Jinja-style ``{{ placeholder }}`` fields.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "authenticate.Organization",
        on_delete=models.CASCADE,
        related_name="document_templates",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="document_templates_created",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    file = models.FileField(upload_to=document_template_upload_to)
    original_filename = models.CharField(max_length=255, blank=True, default="")
    file_size = models.PositiveIntegerField(default=0)
    content_type = models.CharField(
        max_length=128,
        default="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text='Shape: {"placeholders": [...], "variables": {name: {description, required, example}}}',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"DocumentTemplate({self.name}, org={self.organization_id})"


class AgentDocumentTemplateAssignment(models.Model):
    """
    Attach a document template to an agent with per-assignment usage instructions.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(
        "ai_layers.Agent",
        on_delete=models.CASCADE,
        related_name="document_template_assignments",
    )
    template = models.ForeignKey(
        DocumentTemplate,
        on_delete=models.CASCADE,
        related_name="agent_assignments",
    )
    usage_instructions = models.TextField(
        blank=True,
        default="",
        help_text="When and how the AI should use this template for this agent.",
    )
    is_enabled = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="document_template_assignments_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["agent", "template"],
                name="document_templates_unique_agent_template",
            )
        ]
        ordering = ["-created_at"]

    def clean(self) -> None:
        from django.core.exceptions import ValidationError

        if self.agent_id and self.template_id:
            agent_org = getattr(self.agent, "organization_id", None)
            tmpl_org = getattr(self.template, "organization_id", None)
            if agent_org is not None and agent_org != tmpl_org:
                raise ValidationError(
                    "Agent and template must belong to the same organization."
                )

    def __str__(self) -> str:
        return f"AgentDocumentTemplateAssignment(agent={self.agent_id}, template={self.template_id})"
