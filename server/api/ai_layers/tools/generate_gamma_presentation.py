"""
Tool: generate_gamma_attachment

Generates a Gamma file (presentation or document) via the public API,
downloads the export (PDF by default, PPTX optional), stores it as a
MessageAttachment, and returns attachment metadata for download in chat.

The public tool name is generate_gamma_attachment. generate_gamma_presentation
is kept as a registry alias for agents/lines that still have the old name.
"""

from __future__ import annotations

import logging
import os
import re
import time
import uuid
from datetime import timedelta
from typing import Literal

import requests
from django.core.files.base import ContentFile
from django.utils import timezone
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_SLUG_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")

GAMMA_API_BASE = "https://public-api.gamma.app/v1.0"
POLL_INTERVAL_SECONDS = 10
MAX_WAIT_SECONDS = 360

ExportFormat = Literal["pdf", "pptx"]
GammaFormat = Literal["document", "presentation"]
TextMode = Literal["generate", "condense", "preserve"]

_CARD_DIMENSIONS: dict[GammaFormat, str] = {
    "presentation": "16x9",
    "document": "pageless",
}

PDF_CONTENT_TYPE = "application/pdf"
PPTX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)

_CONTENT_TYPES: dict[ExportFormat, str] = {
    "pdf": PDF_CONTENT_TYPE,
    "pptx": PPTX_CONTENT_TYPE,
}


class GenerateGammaAttachmentParams(BaseModel):
    input_text: str = Field(
        description=(
            "Topic, outline, or full content to generate from. "
            "Can be a short topic or a detailed outline; use \\n---\\n to hint card breaks."
        ),
    )
    format: GammaFormat = Field(
        default="presentation",
        description=(
            "Gamma layout: 'presentation' for slides (16:9), 'document' for a "
            "pageless document. Choose from the user's request."
        ),
    )
    title: str = Field(
        default="",
        description="Optional custom title for the generated file (1-500 chars).",
    )
    num_cards: int = Field(
        default=10,
        ge=1,
        le=60,
        description="Target number of cards/sections (default 10).",
    )
    text_mode: TextMode = Field(
        default="generate",
        description=(
            "How Gamma interprets input_text: 'generate' expands, 'condense' "
            "summarizes, 'preserve' keeps text close to the input."
        ),
    )
    language: str = Field(
        default="en",
        description="Output language code (e.g. 'en', 'es', 'es-mx', 'pt-br').",
    )
    additional_instructions: str = Field(
        default="",
        description="Optional style/layout guidance for Gamma (max 5000 chars).",
    )
    export_format: ExportFormat = Field(
        default="pdf",
        description=(
            "Download format. Default 'pdf' for sharing. Use 'pptx' only when "
            "the user needs an editable PowerPoint (presentations)."
        ),
    )
    output_filename: str = Field(
        default="",
        description=(
            "Optional download filename. Extension is forced to match export_format "
            "(.pdf or .pptx)."
        ),
    )


class GenerateGammaAttachmentResult(BaseModel):
    attachment_id: str
    name: str
    content: str
    content_type: str
    format: GammaFormat
    export_format: ExportFormat
    gamma_url: str = ""
    generation_id: str = ""


def _api_key() -> str:
    key = (os.environ.get("GAMMA_API_KEY") or "").strip()
    if not key or key == "__UNSET__":
        raise ValueError("GAMMA_API_KEY is not configured")
    return key


def _headers(api_key: str) -> dict[str, str]:
    return {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _raise_for_gamma_status(resp: requests.Response, *, action: str) -> None:
    if resp.status_code == 401:
        raise ValueError("Gamma API authentication failed (invalid or missing API key).")
    if resp.status_code == 402:
        raise ValueError("Gamma workspace has insufficient credits.")
    if resp.status_code == 403:
        raise ValueError("Gamma API access denied or feature not available for this workspace.")
    if resp.status_code >= 400:
        detail = (resp.text or "").strip()[:500]
        raise ValueError(f"Gamma {action} failed (HTTP {resp.status_code}): {detail or 'unknown error'}")


def _create_generation(
    *,
    api_key: str,
    input_text: str,
    title: str,
    num_cards: int,
    text_mode: TextMode,
    language: str,
    additional_instructions: str,
    export_format: ExportFormat,
    gamma_format: GammaFormat,
) -> str:
    body: dict = {
        "inputText": input_text,
        "textMode": text_mode,
        "format": gamma_format,
        "exportAs": export_format,
        "numCards": num_cards,
        "cardOptions": {"dimensions": _CARD_DIMENSIONS[gamma_format]},
        "sharingOptions": {"externalAccess": "noAccess"},
        "textOptions": {"language": language or "en"},
    }
    if title.strip():
        body["title"] = title.strip()[:500]
    if additional_instructions.strip():
        body["additionalInstructions"] = additional_instructions.strip()[:5000]

    resp = requests.post(
        f"{GAMMA_API_BASE}/generations",
        headers=_headers(api_key),
        json=body,
        timeout=60,
    )
    _raise_for_gamma_status(resp, action="generation create")
    data = resp.json()
    generation_id = data.get("generationId")
    if not generation_id:
        raise ValueError("Gamma did not return a generationId.")
    return str(generation_id)


def _poll_generation(api_key: str, generation_id: str) -> dict:
    elapsed = 0
    while elapsed <= MAX_WAIT_SECONDS:
        resp = requests.get(
            f"{GAMMA_API_BASE}/generations/{generation_id}",
            headers=_headers(api_key),
            timeout=60,
        )
        _raise_for_gamma_status(resp, action="generation status")
        data = resp.json()
        status = (data.get("status") or "").lower()
        if status == "completed":
            return data
        if status == "failed":
            err = data.get("error") or {}
            msg = err.get("message") if isinstance(err, dict) else str(err)
            raise ValueError(f"Gamma generation failed: {msg or 'unknown error'}")
        logger.info(
            "Gamma generation %s pending (%ds elapsed)",
            generation_id,
            elapsed,
        )
        time.sleep(POLL_INTERVAL_SECONDS)
        elapsed += POLL_INTERVAL_SECONDS

    raise ValueError("Gamma generation timed out after 6 minutes.")


def _download_export(export_url: str) -> bytes:
    resp = requests.get(export_url, timeout=120)
    if resp.status_code >= 400:
        raise ValueError(
            f"Failed to download Gamma export (HTTP {resp.status_code})."
        )
    raw = resp.content or b""
    if not raw:
        raise ValueError("Gamma export download returned empty content.")
    return raw


def _normalize_filename(
    output_filename: str,
    export_format: ExportFormat,
    gamma_format: GammaFormat = "presentation",
) -> str:
    ext = f".{export_format}"
    default = f"{'document' if gamma_format == 'document' else 'presentation'}{ext}"
    fname = (output_filename or "").strip() or default
    lower = fname.lower()
    if lower.endswith(".pdf") or lower.endswith(".pptx"):
        fname = fname.rsplit(".", 1)[0] + ext
    else:
        fname = f"{fname}{ext}"
    fname = _SLUG_SAFE.sub("_", fname)[:200] or default
    if not fname.lower().endswith(ext):
        fname = f"{fname}{ext}"
    return fname


def _generate_gamma_attachment_impl(
    *,
    input_text: str,
    title: str,
    num_cards: int,
    text_mode: TextMode,
    language: str,
    additional_instructions: str,
    export_format: ExportFormat,
    output_filename: str,
    conversation_id: str,
    user_id: int | None,
    agent_slug: str | None,
    gamma_format: GammaFormat = "presentation",
) -> GenerateGammaAttachmentResult:
    from django.contrib.auth.models import User

    from api.messaging.models import Conversation, MessageAttachment

    input_text = (input_text or "").strip()
    if not input_text:
        raise ValueError("input_text is required")

    if export_format not in ("pdf", "pptx"):
        raise ValueError("export_format must be 'pdf' or 'pptx'")
    if gamma_format not in ("document", "presentation"):
        raise ValueError("format must be 'document' or 'presentation'")

    try:
        conversation = Conversation.objects.select_related(
            "organization", "chat_widget"
        ).get(id=conversation_id)
    except Conversation.DoesNotExist:
        raise ValueError("Conversation not found")

    api_key = _api_key()
    generation_id = _create_generation(
        api_key=api_key,
        input_text=input_text,
        title=title,
        num_cards=num_cards,
        text_mode=text_mode,
        language=language,
        additional_instructions=additional_instructions,
        export_format=export_format,
        gamma_format=gamma_format,
    )
    status_data = _poll_generation(api_key, generation_id)
    export_url = (status_data.get("exportUrl") or "").strip()
    if not export_url:
        raise ValueError(
            "Gamma generation completed but no exportUrl was returned. "
            "Ensure exportAs was set on the request."
        )
    raw = _download_export(export_url)

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

    fname = _normalize_filename(output_filename, export_format, gamma_format)
    stem = fname[: -len(f".{export_format}")]
    storage_name = f"{stem}-{uuid.uuid4().hex[:8]}.{export_format}"
    content_type = _CONTENT_TYPES[export_format]

    expires_at = timezone.now() + timedelta(days=365 * 10)
    file_obj = ContentFile(raw, name=storage_name)
    attachment = MessageAttachment.objects.create(
        conversation=conversation,
        user=user,
        agent=agent_obj,
        kind="file",
        file=file_obj,
        content_type=content_type,
        expires_at=expires_at,
        metadata={
            "source": "generate_gamma_attachment",
            "format": gamma_format,
            "export_format": export_format,
            "generation_id": generation_id,
            "gamma_id": status_data.get("gammaId") or "",
            "gamma_url": status_data.get("gammaUrl") or "",
        },
    )
    content_url = attachment.file.url if attachment.file else ""
    return GenerateGammaAttachmentResult(
        attachment_id=str(attachment.id),
        name=fname,
        content=content_url,
        content_type=content_type,
        format=gamma_format,
        export_format=export_format,
        gamma_url=str(status_data.get("gammaUrl") or ""),
        generation_id=generation_id,
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
            "generate_gamma_attachment requires conversation_id in tool context"
        )

    def generate_gamma_attachment(
        input_text: str,
        format: GammaFormat = "presentation",
        title: str = "",
        num_cards: int = 10,
        text_mode: TextMode = "generate",
        language: str = "en",
        additional_instructions: str = "",
        export_format: ExportFormat = "pdf",
        output_filename: str = "",
    ) -> GenerateGammaAttachmentResult:
        return _generate_gamma_attachment_impl(
            input_text=input_text,
            title=title,
            num_cards=num_cards,
            text_mode=text_mode,
            language=language,
            additional_instructions=additional_instructions,
            export_format=export_format,
            output_filename=output_filename,
            conversation_id=conversation_id,
            user_id=user_id,
            agent_slug=agent_slug,
            gamma_format=format,
        )

    return {
        "name": "generate_gamma_attachment",
        "description": (
            "Create a downloadable Gamma file. Pass input_text (topic or outline) "
            "and format: 'presentation' for slides or 'document' for a pageless "
            "document. Default export_format is 'pdf'; use 'pptx' only when the "
            "user needs an editable PowerPoint. Generation can take up to a few "
            "minutes. After success, include in your reply: "
            "[Download file](attachment:<attachment_id>). "
            "Files start as personal; call update_attachment_visibility if other "
            "org members need to list or receive the file."
        ),
        "parameters": GenerateGammaAttachmentParams,
        "function": generate_gamma_attachment,
    }
