"""
Tool: generate_excel_file

Builds an Excel (.xlsx) workbook from structured sheet data, stores the result as a
MessageAttachment, and returns attachment metadata for all channels.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import timedelta

from django.core.files.base import ContentFile
from django.utils import timezone
from pydantic import BaseModel, Field

from api.utils.spreadsheet_tools import (
    XLSX_CONTENT_TYPE,
    build_xlsx_bytes_from_sheets,
    parse_sheets_json,
)

logger = logging.getLogger(__name__)

_SLUG_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


class GenerateExcelFileParams(BaseModel):
    sheets_json: str = Field(
        description=(
            "JSON array of sheet objects. Each object has name, optional headers, "
            "and rows. Example: "
            '[{"name":"Sales","headers":["Month","Revenue"],"rows":[["Jan",1000]]}]'
        )
    )
    output_filename: str = Field(
        default="spreadsheet.xlsx",
        description="Desired download filename (must end with .xlsx).",
    )


class GenerateExcelFileResult(BaseModel):
    attachment_id: str
    name: str
    content: str
    content_type: str
    extension: str
    warnings: list[str] = Field(default_factory=list)


def _generate_excel_file_impl(
    *,
    sheets_json: str,
    output_filename: str,
    conversation_id: str,
    user_id: int | None,
    agent_slug: str | None,
) -> GenerateExcelFileResult:
    from django.contrib.auth.models import User

    from api.messaging.models import Conversation, MessageAttachment

    try:
        conversation = Conversation.objects.select_related(
            "organization", "chat_widget"
        ).get(id=conversation_id)
    except Conversation.DoesNotExist:
        raise ValueError("Conversation not found")

    try:
        sheets = parse_sheets_json(sheets_json)
        xlsx_bytes = build_xlsx_bytes_from_sheets(sheets)
    except Exception as e:
        logger.exception("generate_excel_file conversion failed")
        raise ValueError(f"Excel conversion failed: {e}") from e

    fname = (output_filename or "spreadsheet.xlsx").strip()
    if not fname.lower().endswith(".xlsx"):
        fname = f"{fname}.xlsx"
    fname = _SLUG_SAFE.sub("_", fname)[:200] or "spreadsheet.xlsx"
    safe_stem = fname[:-5] if fname.lower().endswith(".xlsx") else fname
    storage_name = f"{safe_stem}-{uuid.uuid4().hex[:8]}.xlsx"

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
    file_obj = ContentFile(xlsx_bytes, name=storage_name)
    attachment = MessageAttachment.objects.create(
        conversation=conversation,
        user=user,
        agent=agent_obj,
        kind="file",
        file=file_obj,
        content_type=XLSX_CONTENT_TYPE,
        expires_at=expires_at,
        metadata={
            "source": "generate_excel_file",
            "output_format": "xlsx",
            "sheet_count": len(sheets),
        },
    )
    content_url = attachment.file.url if attachment.file else ""
    return GenerateExcelFileResult(
        attachment_id=str(attachment.id),
        name=fname,
        content=content_url,
        content_type=XLSX_CONTENT_TYPE,
        extension="xlsx",
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
            "generate_excel_file requires conversation_id in tool context"
        )

    def generate_excel_file(
        sheets_json: str,
        output_filename: str = "spreadsheet.xlsx",
    ) -> GenerateExcelFileResult:
        return _generate_excel_file_impl(
            sheets_json=sheets_json,
            output_filename=output_filename,
            conversation_id=conversation_id,
            user_id=user_id,
            agent_slug=agent_slug,
        )

    return {
        "name": "generate_excel_file",
        "description": (
            "Create an Excel (.xlsx) spreadsheet from structured sheet data. "
            "Pass sheets_json as a JSON array of sheet objects with name, optional "
            "headers, and rows. Returns attachment_id and a download URL. After "
            "generating, include in your reply: "
            "[Download spreadsheet](attachment:<attachment_id>)."
        ),
        "parameters": GenerateExcelFileParams,
        "function": generate_excel_file,
    }
