"""
Tool: generate_text_file

Writes a UTF-8 text file (CSV, JSON, HTML, markdown, etc.), stores it as a
MessageAttachment, and returns attachment metadata for all channels.
"""

from __future__ import annotations

import mimetypes
import re
import uuid
from datetime import timedelta

from django.core.files.base import ContentFile
from django.utils import timezone
from pydantic import BaseModel, Field, field_validator

_SLUG_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")

ALLOWED_TEXT_EXTENSIONS: frozenset[str] = frozenset(
    {
        "txt",
        "md",
        "markdown",
        "csv",
        "tsv",
        "json",
        "jsonl",
        "html",
        "htm",
        "xml",
        "svg",
        "css",
        "js",
        "mjs",
        "cjs",
        "ts",
        "tsx",
        "jsx",
        "yaml",
        "yml",
        "toml",
        "ini",
        "cfg",
        "conf",
        "log",
        "ics",
        "vcf",
        "rtf",
        "tex",
        "rst",
        "graphql",
        "proto",
        "py",
        "rb",
        "go",
        "rs",
        "java",
        "c",
        "h",
        "cpp",
        "hpp",
        "cc",
        "hh",
        "sh",
        "bash",
        "zsh",
        "ps1",
        "scss",
        "less",
        "sass",
        "vue",
        "svelte",
        "kt",
        "kts",
        "swift",
        "php",
        "r",
        "lua",
        "pl",
        "pm",
        "sql",
        "env",
        "properties",
        "ndjson",
        "geojson",
        "kml",
        "gpx",
        "opml",
        "rss",
        "atom",
        "srt",
        "vtt",
        "diff",
        "patch",
        "gitignore",
        "dockerfile",
        "makefile",
        "cmake",
        "gradle",
    }
)

_MIME_OVERRIDES: dict[str, str] = {
    "md": "text/markdown",
    "markdown": "text/markdown",
    "csv": "text/csv",
    "tsv": "text/tab-separated-values",
    "json": "application/json",
    "jsonl": "application/jsonl",
    "ndjson": "application/x-ndjson",
    "geojson": "application/geo+json",
    "html": "text/html",
    "htm": "text/html",
    "xml": "application/xml",
    "svg": "application/xml",
    "yaml": "application/yaml",
    "yml": "application/yaml",
    "ics": "text/calendar",
    "vcf": "text/vcard",
    "js": "text/javascript",
    "mjs": "text/javascript",
    "cjs": "text/javascript",
    "ts": "text/plain",
    "tsx": "text/plain",
    "jsx": "text/plain",
    "css": "text/css",
    "sql": "application/sql",
    "txt": "text/plain",
}


def normalize_text_extension(raw: str) -> str:
    ext = (raw or "").strip().lower().lstrip(".")
    if ext not in ALLOWED_TEXT_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_TEXT_EXTENSIONS))
        raise ValueError(
            f"Unsupported text extension '{raw}'. Allowed: {allowed}"
        )
    return ext


def content_type_for_text_extension(ext: str) -> str:
    override = _MIME_OVERRIDES.get(ext)
    if override:
        return override
    guessed, _ = mimetypes.guess_type(f"file.{ext}")
    ctype = (guessed or "").lower().split(";")[0].strip()
    if (
        not ctype
        or ctype.startswith("image/")
        or ctype.startswith("audio/")
        or ctype.startswith("video/")
    ):
        return "text/plain"
    return ctype


class GenerateTextFileParams(BaseModel):
    content: str = Field(
        description="Full UTF-8 text body of the file (CSV, JSON, HTML, markdown, etc.)."
    )
    extension: str = Field(
        description=(
            "File extension without a leading dot. Examples: csv, json, html, md, txt, xml, yaml."
        ),
        json_schema_extra={"enum": sorted(ALLOWED_TEXT_EXTENSIONS)},
    )
    filename: str = Field(
        default="file",
        description="Desired download name. Extension is added from 'extension' if missing.",
    )

    @field_validator("extension")
    @classmethod
    def _validate_extension(cls, value: str) -> str:
        return normalize_text_extension(value)


class GenerateTextFileResult(BaseModel):
    attachment_id: str
    name: str
    content: str
    content_type: str
    extension: str
    warnings: list[str] = Field(default_factory=list)


def _generate_text_file_impl(
    *,
    content: str,
    extension: str,
    filename: str,
    conversation_id: str,
    user_id: int | None,
    agent_slug: str | None,
) -> GenerateTextFileResult:
    from django.contrib.auth.models import User

    from api.messaging.models import Conversation, MessageAttachment

    ext = normalize_text_extension(extension)
    try:
        conversation = Conversation.objects.select_related(
            "organization", "chat_widget"
        ).get(id=conversation_id)
    except Conversation.DoesNotExist:
        raise ValueError("Conversation not found")

    fname = (filename or "file").strip() or "file"
    suffix = f".{ext}"
    if not fname.lower().endswith(suffix):
        fname = f"{fname}{suffix}"
    fname = _SLUG_SAFE.sub("_", fname)[:200] or f"file{suffix}"
    stem = fname[: -len(suffix)] if fname.lower().endswith(suffix) else fname
    storage_name = f"{stem}-{uuid.uuid4().hex[:8]}{suffix}"

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

    body = content if isinstance(content, str) else str(content)
    file_bytes = body.encode("utf-8")
    ctype = content_type_for_text_extension(ext)
    expires_at = timezone.now() + timedelta(days=365 * 10)
    file_obj = ContentFile(file_bytes, name=storage_name)
    attachment = MessageAttachment.objects.create(
        conversation=conversation,
        user=user,
        agent=agent_obj,
        kind="file",
        file=file_obj,
        content_type=ctype,
        visibility=MessageAttachment.Visibility.PERSONAL,
        expires_at=expires_at,
        metadata={
            "source": "generate_text_file",
            "output_format": ext,
        },
    )
    content_url = attachment.file.url if attachment.file else ""
    return GenerateTextFileResult(
        attachment_id=str(attachment.id),
        name=fname,
        content=content_url,
        content_type=ctype,
        extension=ext,
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
            "generate_text_file requires conversation_id in tool context"
        )

    def generate_text_file(
        content: str,
        extension: str,
        filename: str = "file",
    ) -> GenerateTextFileResult:
        return _generate_text_file_impl(
            content=content,
            extension=extension,
            filename=filename,
            conversation_id=conversation_id,
            user_id=user_id,
            agent_slug=agent_slug,
        )

    return {
        "name": "generate_text_file",
        "description": (
            "Create a downloadable UTF-8 text file (HTML, CSV, JSON, markdown, txt, "
            "XML, YAML, source code, etc.). Pass the full file body as content, an "
            "allowed extension, and an optional filename. Do not use this for Word "
            "(.docx) or Excel (.xlsx); use generate_document_file or "
            "generate_excel_file instead. Returns attachment_id and a download URL. "
            "After generating, include in your reply: "
            "[Download file](attachment:<attachment_id>). "
            "Files start as personal; call update_attachment_visibility if other "
            "org members need to list or receive the file."
        ),
        "parameters": GenerateTextFileParams,
        "function": generate_text_file,
    }
