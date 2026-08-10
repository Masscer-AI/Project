"""
Tool: read_knowledge_base_document

Returns the full text of a knowledge-base document the authenticated user can access.
Separate from rag_query (agent vector memory) and from list_knowledge_base_documents.
"""

from __future__ import annotations

import json
import logging

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ReadKnowledgeBaseDocumentParams(BaseModel):
    document_id: int = Field(
        description="Numeric id of the knowledge-base document (from list_knowledge_base_documents)."
    )


def _read_impl(*, user_id: int, document_id: int) -> str:
    from django.contrib.auth.models import User

    from api.rag.access import (
        document_belongs_to_payload,
        user_can_access_document,
    )
    from api.rag.models import Document

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        raise ValueError("User not found")

    try:
        doc = Document.objects.select_related(
            "organization", "created_by", "collection"
        ).prefetch_related("allowed_roles").get(id=document_id)
    except Document.DoesNotExist:
        raise ValueError("Document not found")

    if not user_can_access_document(user, doc):
        raise ValueError("Document not accessible")

    return json.dumps(
        {
            "id": doc.id,
            "name": doc.name or "",
            "brief": doc.brief or "",
            "total_tokens": doc.total_tokens,
            "content_type": doc.content_type or "",
            "belongs_to": document_belongs_to_payload(doc, user),
            "text": doc.text or "",
            "message": (
                "Full document text returned. "
                "For semantic search over trained agent memory, use rag_query instead."
            ),
        },
        ensure_ascii=False,
    )


def get_tool(
    user_id: int | None = None,
    **kwargs,
) -> dict:
    if user_id is None:
        raise ValueError(
            "read_knowledge_base_document requires user_id in tool context"
        )

    def read_knowledge_base_document(document_id: int) -> str:
        return _read_impl(user_id=user_id, document_id=int(document_id))

    return {
        "name": "read_knowledge_base_document",
        "description": (
            "Read the full text of a knowledge-base document by id. "
            "The user must have access (personal / organization / roles). "
            "Prefer list_knowledge_base_documents first to discover ids and briefs. "
            "For semantic chunk search over the agent's trained memory, use rag_query."
        ),
        "parameters": ReadKnowledgeBaseDocumentParams,
        "function": read_knowledge_base_document,
    }
