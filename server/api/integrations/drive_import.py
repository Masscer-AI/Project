"""
Import and sync RAG documents from Google Drive.
"""

from __future__ import annotations

import io
import logging

from django.contrib.auth.models import User

from api.integrations.models import IntegrationProvider
from api.integrations.providers import IntegrationProviderError, get_provider
from api.integrations.services import (
    ensure_valid_access_token,
    get_google_client_id,
    get_google_client_secret,
    get_integration_for_owner,
    parse_owner_type,
)
from api.rag.actions import read_file_content
from api.rag.models import Collection, Document

logger = logging.getLogger(__name__)


def _drive_provider(access_token: str):
    return get_provider(
        IntegrationProvider.GOOGLE_DRIVE,
        client_id=get_google_client_id(),
        client_secret=get_google_client_secret(),
        redirect_uri="",
        access_token=access_token,
    )


def get_drive_integration_for_owner(
    *,
    user: User,
    owner_type: str,
    organization,
) -> Integration | None:
    owner = parse_owner_type(owner_type)
    return get_integration_for_owner(
        provider=IntegrationProvider.GOOGLE_DRIVE,
        owner_type=owner,
        user=user,
        organization=organization,
    )


def list_drive_files_for_user(
    *,
    user: User,
    owner_type: str,
    organization,
    limit: int = 50,
) -> list[dict]:
    integration = get_drive_integration_for_owner(
        user=user,
        owner_type=owner_type,
        organization=organization,
    )
    if integration is None:
        raise IntegrationProviderError("No Google Drive integration connected for this owner.")

    access_token = ensure_valid_access_token(integration)
    provider = _drive_provider(access_token)
    files = provider.list_files(access_token, limit=limit)
    return [f for f in files if f.get("mimeType") != "application/vnd.google-apps.folder"]


def _extract_text_from_drive_bytes(
    content: bytes,
    file_name: str,
    mime_type: str,
) -> tuple[str, str]:
    """Return (text, resolved_file_name)."""
    if mime_type.startswith("text/") or mime_type in (
        "application/json",
        "application/xml",
    ):
        for encoding in ("utf-8", "latin-1"):
            try:
                return content.decode(encoding).strip(), file_name
            except UnicodeDecodeError:
                continue
        return content.decode("utf-8", errors="replace").strip(), file_name

    buffer = io.BytesIO(content)
    buffer.name = file_name
    text, resolved_name = read_file_content(buffer)
    return text.strip(), resolved_name


def import_drive_file_to_document(
    *,
    user: User,
    file_id: str,
    owner_type: str,
    organization,
) -> tuple[Document, bool]:
    """
    Download a Drive file and create or update a RAG Document.

    Returns (document, created).
    """
    integration = get_drive_integration_for_owner(
        user=user,
        owner_type=owner_type,
        organization=organization,
    )
    if integration is None:
        raise IntegrationProviderError("No Google Drive integration connected for this owner.")

    access_token = ensure_valid_access_token(integration)
    provider = _drive_provider(access_token)
    content, file_name, mime_type = provider.download_file_content(access_token, file_id)
    meta = provider.get_file_metadata(access_token, file_id)
    modified_time = meta.get("modifiedTime") or ""

    text, file_name = _extract_text_from_drive_bytes(content, file_name, mime_type)
    if not text:
        raise IntegrationProviderError("Drive file has no extractable text content.")

    collection, _ = Collection.get_or_create_personal_collection(user=user)
    if not collection:
        raise IntegrationProviderError("Could not resolve knowledge base collection.")

    existing = Document.objects.filter(
        collection=collection,
        drive_file_id=file_id,
    ).first()

    if existing:
        existing.clear_chunks()
        existing.text = text.replace("\0", "")
        existing.name = file_name
        existing.content_type = mime_type
        existing.drive_integration = integration
        existing.drive_modified_time = modified_time
        existing.total_tokens = None
        existing.save()
        existing.reindex_rag()
        from api.rag.tasks import async_generate_document_brief

        async_generate_document_brief.delay(existing.id)
        return existing, False

    document = Document.objects.create(
        collection=collection,
        text=text.replace("\0", ""),
        name=file_name,
        content_type=mime_type,
        drive_file_id=file_id,
        drive_integration=integration,
        drive_modified_time=modified_time,
    )
    # post_save signal runs add_to_rag + brief
    return document, True


def sync_document_from_drive(document: Document) -> Document:
    """Re-download linked Drive file and re-index the document."""
    if not document.drive_file_id:
        raise IntegrationProviderError("Document is not linked to Google Drive.")

    integration = document.drive_integration
    if integration is None:
        raise IntegrationProviderError("Drive integration reference is missing.")

    access_token = ensure_valid_access_token(integration)
    provider = _drive_provider(access_token)
    content, file_name, mime_type = provider.download_file_content(
        access_token,
        document.drive_file_id,
    )
    meta = provider.get_file_metadata(access_token, document.drive_file_id)

    text, file_name = _extract_text_from_drive_bytes(content, file_name, mime_type)
    if not text:
        raise IntegrationProviderError("Drive file has no extractable text content.")

    document.clear_chunks()
    document.text = text.replace("\0", "")
    document.name = file_name
    document.content_type = mime_type
    document.drive_modified_time = meta.get("modifiedTime") or ""
    document.total_tokens = None
    document.save()
    document.reindex_rag()

    from api.rag.tasks import async_generate_document_brief

    async_generate_document_brief.delay(document.id)
    return document
