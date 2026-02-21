"""
Tool for reading message attachments by ID and answering questions about them.

Supports images (via vision) and documents (PDF, DOCX, etc. via input_file).
Uses OpenAI to analyze the content and answer the provided question.
"""

from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING

from openai import OpenAI
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ReadAttachmentParams(BaseModel):
    """Parameters for the read_attachment tool."""

    attachment_id: str = Field(
        description="The UUID of the attachment to read. Use one of the attachment IDs provided by the user."
    )
    question: str = Field(
        description="A specific question about the document or image content. Be precise."
    )


class DocumentAnswer(BaseModel):
    """Schema for document answer from OpenAI."""

    answer: str


class ReadAttachmentResult(BaseModel):
    """Result returned by read_attachment."""

    answer: str = Field(description="The answer to the question based on the attachment content")
    message: str = Field(
        default="Successfully analyzed attachment",
        description="Status message",
    )


# ---------------------------------------------------------------------------
# Tool implementation
# ---------------------------------------------------------------------------


def _read_attachment_impl(
    attachment_id: str,
    question: str,
    conversation_id: str,
    user_id: int | None,
) -> ReadAttachmentResult:
    """
    Read an attachment and answer a question about it.

    Validates that the attachment belongs to the conversation.
    For images: uses vision API. For documents: uses input_file with base64.
    """
    from api.messaging.models import MessageAttachment

    try:
        att = MessageAttachment.objects.get(id=attachment_id)
    except MessageAttachment.DoesNotExist:
        raise ValueError(f"Attachment {attachment_id} not found")

    if str(att.conversation_id) != str(conversation_id):
        raise ValueError(
            f"Attachment {attachment_id} does not belong to this conversation"
        )

    if user_id is not None and att.user_id is not None and att.user_id != user_id:
        raise ValueError(f"Attachment {attachment_id} is not accessible")

    kind = getattr(att, "kind", None) or "file"
    if kind == "rag_document":
        return _process_rag_document(att, question)
    if kind == "website":
        return _process_website(att, question)

    # Default: file attachment (image or generic document)
    is_image = bool(att.content_type and att.content_type.startswith("image/"))
    return _process_image(att, question) if is_image else _process_document(att, question)


def _process_image(att, question: str) -> ReadAttachmentResult:
    """Process image via vision API."""
    import os

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    if not att.file:
        raise ValueError(f"File content not available for attachment {att.id}")

    with att.file.open("rb") as f:
        raw = f.read()
    b64 = base64.b64encode(raw).decode("ascii")
    mime = att.content_type or "image/png"
    data_url = f"data:{mime};base64,{b64}"

    content = [
        {"type": "input_text", "text": question},
        {"type": "input_image", "image_url": data_url},
    ]

    try:
        response = client.responses.create(
            model="gpt-4o",
            instructions="Answer the user's question about the image. Be concise and accurate. Extract specific information when requested. If the information is not visible, say so clearly.",
            input=[{"role": "user", "content": content}],
        )
        answer_text = _extract_output_text(response)
        if not answer_text:
            answer_text = "Could not extract a response from the model."
        return ReadAttachmentResult(
            answer=answer_text,
            message=f"Successfully analyzed image",
        )
    except Exception as e:
        logger.exception("Error analyzing image %s", att.id)
        raise ValueError(f"Failed to analyze image: {str(e)}")


def _process_document(att, question: str) -> ReadAttachmentResult:
    """Process document (PDF, DOCX, etc.) via input_file."""
    import os

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    if not att.file:
        raise ValueError(f"File content not available for attachment {att.id}")

    with att.file.open("rb") as f:
        raw = f.read()
    b64 = base64.b64encode(raw).decode("ascii")
    mime = att.content_type or "application/octet-stream"
    filename = att.file.name.split("/")[-1] if att.file.name else f"file_{att.id}"

    content = [
        {"type": "input_text", "text": question},
        {
            "type": "input_file",
            "filename": filename,
            "file_data": f"data:{mime};base64,{b64}",
        },
    ]

    try:
        response = client.responses.create(
            model="gpt-4o",
            instructions="Answer the user's question about the document. Be concise and accurate. Extract specific information when requested. If the information is not in the document, state that clearly.",
            input=[{"role": "user", "content": content}],
        )
        answer_text = _extract_output_text(response)
        if not answer_text:
            answer_text = "Could not extract a response from the model."
        return ReadAttachmentResult(
            answer=answer_text,
            message=f"Successfully analyzed {filename}",
        )
    except Exception as e:
        logger.exception("Error analyzing document %s", att.id)
        raise ValueError(f"Failed to analyze document: {str(e)}")


def _search_document_collection(doc, question: str) -> str:
    """
    If the document's collection has a ChromaDB index, run a semantic search
    scoped to this document and return the matching chunks as extra context.
    Returns an empty string when ChromaDB is unavailable or nothing is found.
    """
    try:
        from api.rag.managers import chroma_client

        if not chroma_client:
            return ""

        collection = getattr(doc, "collection", None)
        if not collection or not collection.slug:
            return ""

        results = chroma_client.get_results(
            collection_name=collection.slug,
            query_texts=[question],
            n_results=6,
            where={"extra": doc.get_representation()},
        )

        if not results:
            return ""

        chunks: list[str] = []
        for doc_list in (results.get("documents") or []):
            for text in doc_list:
                if text:
                    chunks.append(text.strip())

        if not chunks:
            metadatas = results.get("metadatas") or []
            for meta_list in metadatas:
                for meta in meta_list:
                    content = meta.get("content", "") if isinstance(meta, dict) else ""
                    if content:
                        chunks.append(content.strip())

        if not chunks:
            return ""

        formatted = "\n---\n".join(chunks)
        return (
            f"\n\n<SEMANTIC_SEARCH_RESULTS query=\"{question}\">\n"
            f"{formatted}\n"
            f"</SEMANTIC_SEARCH_RESULTS>"
        )
    except Exception:
        logger.debug("Collection search failed for document %s", doc.id, exc_info=True)
        return ""


def _process_rag_document(att, question: str) -> ReadAttachmentResult:
    """Process a RAG document: full text + semantic search on its collection."""
    import os

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    doc = getattr(att, "rag_document", None)
    if doc is None:
        raise ValueError(f"RAG document not available for attachment {att.id}")

    text = getattr(doc, "text", "") or ""
    name = getattr(doc, "name", None) or f"document_{doc.id}"

    max_chars = 120_000
    if len(text) > max_chars:
        text = text[:max_chars]

    collection_context = _search_document_collection(doc, question)

    content = [
        {
            "type": "input_text",
            "text": (
                f"Document name: {name}\n\n"
                f"Document text:\n{text}\n\n"
                f"{collection_context}\n\n"
                f"Question: {question}"
            ),
        }
    ]

    try:
        response = client.responses.create(
            model="gpt-4o",
            instructions=(
                "Answer the user's question using the provided document text and "
                "any semantic search results from the document's vector index. "
                "Be concise and accurate. If the answer is not in the text, say so clearly."
            ),
            input=[{"role": "user", "content": content}],
        )
        answer_text = _extract_output_text(response)
        if not answer_text:
            answer_text = "Could not extract a response from the model."
        return ReadAttachmentResult(
            answer=answer_text,
            message="Successfully analyzed RAG document",
        )
    except Exception as e:
        logger.exception("Error analyzing RAG document attachment %s", att.id)
        raise ValueError(f"Failed to analyze RAG document: {str(e)}")


def _process_website(att, question: str) -> ReadAttachmentResult:
    """Fetch a website URL and answer a question about its content."""
    import os

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    url = getattr(att, "url", None) or ""
    if not url:
        raise ValueError(f"URL not available for attachment {att.id}")

    # Prefer stored snapshot (no refetch).
    metadata = getattr(att, "metadata", None) or {}
    text = metadata.get("content") if isinstance(metadata, dict) else None

    if not text:
        # Fallback: fetch live if snapshot missing.
        import re
        import requests
        from html import unescape

        try:
            resp = requests.get(
                url,
                headers={"User-Agent": "masscer/1.0 (+https://masscer.local)"},
                timeout=20,
            )
            resp.raise_for_status()
            html = resp.text or ""
        except Exception as e:
            logger.exception("Error fetching website %s", url)
            raise ValueError(f"Failed to fetch website: {str(e)}")

        # Very lightweight text extraction (no external deps)
        html = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\\1>", " ", html)
        html = re.sub(r"(?is)<br\\s*/?>", "\n", html)
        text = re.sub(r"(?is)<.*?>", " ", html)
        text = unescape(text)
        text = re.sub(r"[ \\t\\r\\f\\v]+", " ", text)
        text = re.sub(r"\\n\\s*\\n+", "\n\n", text).strip()

    max_chars = 120_000
    if len(text) > max_chars:
        text = text[:max_chars]

    content = [
        {
            "type": "input_text",
            "text": (
                f"Website URL: {url}\n\n"
                f"Website text:\n{text}\n\n"
                f"Question: {question}"
            ),
        }
    ]

    try:
        response = client.responses.create(
            model="gpt-4o",
            instructions=(
                "Answer the user's question using only the provided website text. "
                "Be concise and accurate. If the answer is not in the text, say so clearly."
            ),
            input=[{"role": "user", "content": content}],
        )
        answer_text = _extract_output_text(response)
        if not answer_text:
            answer_text = "Could not extract a response from the model."
        return ReadAttachmentResult(
            answer=answer_text,
            message="Successfully analyzed website",
        )
    except Exception as e:
        logger.exception("Error analyzing website attachment %s", att.id)
        raise ValueError(f"Failed to analyze website: {str(e)}")

def _extract_output_text(response) -> str:
    """Extract text content from an OpenAI Responses API response."""
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


# ---------------------------------------------------------------------------
# Tool config
# ---------------------------------------------------------------------------


def get_tool(
    conversation_id: str | None = None,
    user_id: int | None = None,
    **kwargs,
) -> dict:
    """
    Return an AgentTool dict for the read_attachment tool.

    When conversation_id and user_id are provided, the tool validates access.
    """
    if conversation_id is not None and user_id is not None:

        def read_attachment(attachment_id: str, question: str) -> ReadAttachmentResult:
            return _read_attachment_impl(
                attachment_id=attachment_id,
                question=question,
                conversation_id=conversation_id,
                user_id=user_id,
            )

    else:

        def read_attachment(attachment_id: str, question: str) -> ReadAttachmentResult:
            return _read_attachment_impl(
                attachment_id=attachment_id,
                question=question,
                conversation_id=conversation_id or "",
                user_id=user_id,
            )

    return {
        "name": "read_attachment",
        "description": (
            "Read an attachment by its ID and answer a question about it. "
            "Use this when the user has attached documents or images and you need to extract specific information. "
            "Provide the attachment_id (from the list of available IDs) and a specific question."
        ),
        "parameters": ReadAttachmentParams,
        "function": read_attachment,
    }
