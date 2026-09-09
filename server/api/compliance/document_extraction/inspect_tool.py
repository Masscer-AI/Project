"""Inspect a PLD expedient file with gpt-5.6-luna (vision or PDF input_file)."""

from __future__ import annotations

import base64
import logging
import os

from openai import OpenAI
from pydantic import BaseModel, Field

from api.compliance.document_extraction.constants import PLD_EXTRACTION_MODEL_SLUG

logger = logging.getLogger(__name__)


class InspectPldDocumentParams(BaseModel):
    question: str = Field(
        description="Specific question about what is visible in the uploaded file."
    )


class InspectPldDocumentResult(BaseModel):
    answer: str
    message: str = "Successfully analyzed document"


def _extract_output_text(response) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text:
        return output_text.strip()
    chunks = []
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", "") == "message":
            for content in getattr(item, "content", []) or []:
                if getattr(content, "type", "") in ("output_text", "text"):
                    text = getattr(content, "text", "")
                    if text:
                        chunks.append(text)
    return "".join(chunks).strip()


def _usage_tokens(response) -> tuple[int, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0
    prompt = int(getattr(usage, "input_tokens", 0) or 0)
    completion = int(getattr(usage, "output_tokens", 0) or 0)
    return prompt, completion


def _read_pld_file_bytes(doc) -> bytes:
    """Read bytes from storage each call; Django FieldFile cannot reopen a closed handle."""
    field = doc.file
    if not field:
        raise ValueError("File content not available")
    inner = getattr(field, "_file", None)
    if inner is not None:
        try:
            field.close()
        except Exception:
            pass
        field._file = None
    with field.open("rb") as handle:
        raw = handle.read()
    field._file = None
    return raw


def inspect_pld_document_file(
    doc,
    question: str,
    *,
    billing_user_id: int | None = None,
    organization_id=None,
) -> InspectPldDocumentResult:
    raw = _read_pld_file_bytes(doc)
    if not raw:
        raise ValueError("File is empty")

    b64 = base64.b64encode(raw).decode("ascii")
    mime = doc.content_type or "application/octet-stream"
    filename = doc.original_filename or (doc.file.name.split("/")[-1] if doc.file.name else "document")
    is_image = mime.startswith("image/")
    if is_image:
        content = [
            {"type": "input_text", "text": question},
            {"type": "input_image", "image_url": f"data:{mime};base64,{b64}"},
        ]
        instructions = (
            "Answer about what is visible on this identification document. "
            "Be precise. If a field is not visible, say so. Never invent RFC or CURP."
        )
    else:
        content = [
            {"type": "input_text", "text": question},
            {
                "type": "input_file",
                "filename": filename,
                "file_data": f"data:{mime};base64,{b64}",
            },
        ]
        instructions = (
            "Answer about this document. Be precise. If a field is not in the file, "
            "say so. Never invent RFC, CURP, or ownership percentages."
        )

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    try:
        response = client.responses.create(
            model=PLD_EXTRACTION_MODEL_SLUG,
            instructions=instructions,
            input=[{"role": "user", "content": content}],
        )
    except Exception as exc:
        logger.exception("inspect_pld_document failed for %s", doc.id)
        raise ValueError(f"Failed to analyze document: {exc}") from exc

    prompt_tokens, completion_tokens = _usage_tokens(response)
    if billing_user_id and (prompt_tokens or completion_tokens):
        from api.consumption.actions import register_llm_interaction

        register_llm_interaction(
            billing_user_id,
            prompt_tokens,
            completion_tokens,
            PLD_EXTRACTION_MODEL_SLUG,
            organization_id=organization_id,
        )

    answer = _extract_output_text(response) or "Could not extract a response from the model."
    return InspectPldDocumentResult(answer=answer, message=f"Successfully analyzed {filename}")


def make_inspect_tool(doc, *, billing_user_id: int | None, organization_id=None) -> dict:
    def inspect_pld_document(question: str) -> InspectPldDocumentResult:
        return inspect_pld_document_file(
            doc,
            question,
            billing_user_id=billing_user_id,
            organization_id=organization_id,
        )

    return {
        "name": "inspect_pld_document",
        "description": (
            "Read the uploaded PLD file (image or PDF) and answer a question about "
            "visible fields. Call this before producing the final structured extraction."
        ),
        "parameters": InspectPldDocumentParams,
        "function": inspect_pld_document,
    }
