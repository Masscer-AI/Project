"""
Tool: generate_document_file

Converts markdown or HTML document content to DOCX via Pandoc, stores the
result as a MessageAttachment, and returns attachment metadata for all channels
(web, widget, WhatsApp).
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import timedelta
from typing import Literal

from django.core.files.base import ContentFile
from django.utils import timezone
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_SLUG_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")
DocumentExtension = Literal["md", "html"]

DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


class GenerateDocumentFileParams(BaseModel):
    document_string: str = Field(
        description="Full document body in markdown or HTML (complete content to convert)."
    )
    extension: DocumentExtension = Field(
        default="md",
        description="Source format: 'md' for markdown or 'html' for HTML.",
    )
    output_filename: str = Field(
        default="document.docx",
        description="Desired download filename (must end with .docx).",
    )


class GenerateDocumentFileResult(BaseModel):
    attachment_id: str
    name: str
    content: str
    content_type: str
    extension: str
    warnings: list[str] = Field(default_factory=list)


def _generate_document_file_impl(
    *,
    document_string: str,
    extension: DocumentExtension,
    output_filename: str,
    conversation_id: str,
    user_id: int | None,
    agent_slug: str | None,
) -> GenerateDocumentFileResult:
    from django.contrib.auth.models import User

    from api.messaging.models import Conversation, MessageAttachment
    from api.utils.document_tools import convert_document_string_to_docx_bytes

    try:
        conversation = Conversation.objects.select_related(
            "organization", "chat_widget"
        ).get(id=conversation_id)
    except Conversation.DoesNotExist:
        raise ValueError("Conversation not found")

    try:
        docx_bytes = convert_document_string_to_docx_bytes(
            document_string, extension
        )
    except Exception as e:
        logger.exception("generate_document_file conversion failed")
        raise ValueError(f"Document conversion failed: {e}") from e

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

    agent_obj = None
    if agent_slug:
        try:
            from api.ai_layers.models import Agent

            agent_obj = Agent.objects.get(slug=agent_slug)
        except Exception:
            agent_obj = None

    expires_at = timezone.now() + timedelta(days=365 * 10)
    file_obj = ContentFile(docx_bytes, name=storage_name)
    attachment = MessageAttachment.objects.create(
        conversation=conversation,
        user=user,
        agent=agent_obj,
        kind="file",
        file=file_obj,
        content_type=DOCX_CONTENT_TYPE,
        expires_at=expires_at,
        metadata={
            "source": "generate_document_file",
            "input_extension": extension,
            "output_format": "docx",
        },
    )
    content_url = attachment.file.url if attachment.file else ""
    return GenerateDocumentFileResult(
        attachment_id=str(attachment.id),
        name=fname,
        content=content_url,
        content_type=DOCX_CONTENT_TYPE,
        extension=extension,
        warnings=[],
    )


def get_tool(
    conversation_id: str | None = None,
    user_id: int | None = None,
    agent_slug: str | None = None,
    organization_id: str | None = None,
    **kwargs,
) -> dict:
    if not conversation_id:
        raise ValueError(
            "generate_document_file requires conversation_id in tool context"
        )

    def generate_document_file(
        document_string: str,
        extension: DocumentExtension = "md",
        output_filename: str = "document.docx",
    ) -> GenerateDocumentFileResult:
        return _generate_document_file_impl(
            document_string=document_string,
            extension=extension,
            output_filename=output_filename,
            conversation_id=conversation_id,
            user_id=user_id,
            agent_slug=agent_slug,
        )

    return {
        "name": "generate_document_file",
        "description": (
            "Create a Word (.docx) file from scratch. Pass the full document as "
            "document_string in markdown (extension='md') or HTML (extension='html'). "
            "Returns attachment_id and a download URL. After generating, include in your "
            "reply: [Download document](attachment:<attachment_id>)."
        ),
        "parameters": GenerateDocumentFileParams,
        "function": generate_document_file,
    }
