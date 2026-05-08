"""
Tool: render_document_template

Fills an assigned DOCX template with string variables and stores the result
as a MessageAttachment on the conversation.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import timedelta

from django.core.files.base import ContentFile
from django.utils import timezone
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_SLUG_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


class RenderDocumentTemplateParams(BaseModel):
    template_id: str = Field(description="UUID of the template to render (from list_document_templates).")
    variables_json: str = Field(
        default="{}",
        description='JSON object mapping placeholder name to string value, e.g. {"client_name":"ACME","amount":"100"}.',
    )
    output_filename: str = Field(
        default="document.docx",
        description="Desired output file name (must end with .docx).",
    )


class RenderDocumentTemplateResult(BaseModel):
    attachment_id: str
    name: str
    content: str
    content_type: str
    warnings: list[str] = Field(default_factory=list)


def _render_impl(
    *,
    template_id: str,
    variables: dict[str, str],
    output_filename: str,
    conversation_id: str,
    user_id: int | None,
    agent_slug: str | None,
    organization_id: str | None,
) -> RenderDocumentTemplateResult:
    from api.ai_layers.models import Agent
    from api.document_templates.models import AgentDocumentTemplateAssignment, DocumentTemplate
    from api.messaging.models import Conversation, MessageAttachment
    from django.contrib.auth.models import User

    if not agent_slug:
        raise ValueError("agent_slug is required in tool context")

    try:
        conversation = Conversation.objects.select_related("organization", "chat_widget").get(
            id=conversation_id
        )
    except Conversation.DoesNotExist:
        raise ValueError("Conversation not found")

    agent = Agent.objects.filter(slug=agent_slug).select_related("organization").first()
    if not agent:
        raise ValueError("Agent not found")

    assignment = (
        AgentDocumentTemplateAssignment.objects.filter(
            agent=agent,
            template_id=template_id,
            is_enabled=True,
            template__is_active=True,
        )
        .select_related("template")
        .first()
    )
    if not assignment:
        raise ValueError("Template is not assigned to this agent or is disabled")

    template: DocumentTemplate = assignment.template
    if agent.organization_id and template.organization_id != agent.organization_id:
        raise ValueError("Template organization mismatch")

    md = template.metadata or {}
    placeholders = md.get("placeholders") if isinstance(md.get("placeholders"), list) else []
    var_specs = md.get("variables") if isinstance(md.get("variables"), dict) else {}

    warnings: list[str] = []
    coerced: dict[str, str] = {}
    for k, v in (variables or {}).items():
        coerced[str(k)] = "" if v is None else str(v)

    missing_required: list[str] = []
    for ph in placeholders:
        spec = var_specs.get(ph) if isinstance(var_specs.get(ph), dict) else {}
        required = bool(spec.get("required", True)) if isinstance(spec, dict) else True
        if required and not (coerced.get(ph) or "").strip():
            missing_required.append(ph)
    if missing_required:
        raise ValueError(
            "Missing required variables: "
            + ", ".join(missing_required)
            + ". Fill them using information from the conversation."
        )

    unknown = [k for k in coerced if k not in placeholders]
    for u in unknown:
        warnings.append(f"Ignored unknown variable key not in template: {u}")
    render_vars = {ph: coerced.get(ph, "") for ph in placeholders}

    try:
        from api.document_templates.rendering import render_docx_template_to_bytes
    except ImportError as e:
        raise ValueError(
            "Document rendering is not available on this server (missing dependency docxtpl). "
            "Install server dependencies and restart Celery."
        ) from e

    try:
        docx_bytes = render_docx_template_to_bytes(template, render_vars)
    except Exception as e:
        logger.exception("docxtpl render failed for template %s", template_id)
        raise ValueError(f"Template render failed: {e}") from e

    fname = (output_filename or "document.docx").strip()
    if not fname.lower().endswith(".docx"):
        fname = f"{fname}.docx"
    fname = _SLUG_SAFE.sub("_", fname)[:200] or "document.docx"
    safe_stem = fname[:-5] if fname.lower().endswith(".docx") else fname
    storage_name = f"{safe_stem}-{uuid.uuid4().hex[:8]}.docx"

    user = None
    if user_id is not None:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            user = None

    expires_at = timezone.now() + timedelta(days=365 * 10)
    file_obj = ContentFile(docx_bytes, name=storage_name)
    attachment = MessageAttachment.objects.create(
        conversation=conversation,
        user=user,
        agent=agent,
        kind="file",
        file=file_obj,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        expires_at=expires_at,
        metadata={
            "source": "render_document_template",
            "template_id": str(template.id),
            "template_name": template.name,
            "variables": render_vars,
        },
    )
    content_url = attachment.file.url if attachment.file else ""
    return RenderDocumentTemplateResult(
        attachment_id=str(attachment.id),
        name=fname,
        content=content_url,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        warnings=warnings,
    )


def get_tool(
    conversation_id: str | None = None,
    user_id: int | None = None,
    agent_slug: str | None = None,
    organization_id: str | None = None,
    **kwargs,
) -> dict:
    if not conversation_id:
        raise ValueError("render_document_template requires conversation_id in tool context")

    def render_document_template(
        template_id: str,
        variables_json: str = "{}",
        output_filename: str = "document.docx",
    ) -> RenderDocumentTemplateResult:
        raw = (variables_json or "").strip() or "{}"
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"variables_json must be valid JSON: {e}") from e
        if not isinstance(parsed, dict):
            raise ValueError("variables_json must be a JSON object")
        vars_in = {str(k): ("" if v is None else str(v)) for k, v in parsed.items()}
        return _render_impl(
            template_id=template_id,
            variables=vars_in,
            output_filename=output_filename,
            conversation_id=conversation_id,
            user_id=user_id,
            agent_slug=agent_slug,
            organization_id=organization_id,
        )

    return {
        "name": "render_document_template",
        "description": (
            "Render an assigned Word (.docx) template into a filled document. "
            "Pass template_id from list_document_templates and variables_json as a JSON object string "
            "mapping each placeholder name to the final string (e.g. '{\"name\":\"Ada\"}'). "
            "Returns attachment_id and URL for the generated .docx."
        ),
        "parameters": RenderDocumentTemplateParams,
        "function": render_document_template,
    }
