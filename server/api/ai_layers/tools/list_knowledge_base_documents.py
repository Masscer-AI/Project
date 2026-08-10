"""
Tool: list_knowledge_base_documents

Lists knowledge-base documents the authenticated user can access
(personal / organization / roles ACL). Separate from rag_query (agent vector memory).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ListKnowledgeBaseDocumentsParams(BaseModel):
    query: str | None = Field(
        default=None,
        description=(
            "Optional case-insensitive filter matched against document name or brief. "
            "Omit to list all accessible documents."
        ),
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of documents to return.",
    )


def _list_impl(
    *,
    user_id: int,
    query: str | None = None,
    limit: int = 50,
) -> str:
    from django.contrib.auth.models import User
    from django.db.models import Count, Q

    from api.rag.access import (
        document_belongs_to_payload,
        documents_accessible_q,
    )
    from api.rag.models import Document

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        raise ValueError("User not found")

    qs = (
        Document.objects.filter(documents_accessible_q(user))
        .select_related("organization", "created_by", "collection")
        .prefetch_related("allowed_roles")
        .annotate(chunk_count=Count("chunk"))
        .distinct()
        .order_by("-created_at")
    )

    q = (query or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(brief__icontains=q))

    docs = list(qs[:limit])
    items: list[dict[str, Any]] = []
    for doc in docs:
        items.append(
            {
                "id": doc.id,
                "name": doc.name or "",
                "brief": doc.brief or "",
                "total_tokens": doc.total_tokens,
                "chunk_count": getattr(doc, "chunk_count", None),
                "content_type": doc.content_type or "",
                "has_file": bool(doc.file),
                "is_drive_linked": bool(doc.drive_file_id),
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "belongs_to": document_belongs_to_payload(doc, user),
            }
        )

    return json.dumps(
        {
            "count": len(items),
            "documents": items,
            "message": (
                "Listed knowledge-base documents the user can access. "
                "Use read_knowledge_base_document with an id to load full text. "
                "Use rag_query for semantic search over the agent's trained memory "
                "(approved completions), not this document catalog."
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
            "list_knowledge_base_documents requires user_id in tool context"
        )

    def list_knowledge_base_documents(
        query: str | None = None,
        limit: int = 50,
    ) -> str:
        return _list_impl(user_id=user_id, query=query, limit=limit)

    return {
        "name": "list_knowledge_base_documents",
        "description": (
            "List knowledge-base documents the current user can access "
            "(their personal docs, organization-shared docs, or role-scoped docs). "
            "Returns id, name, brief, tokens, chunk_count, and belongs_to "
            "(you / organization / roles). "
            "Does NOT search agent trained memory — use rag_query for that. "
            "To read full text, call read_knowledge_base_document with a document id."
        ),
        "parameters": ListKnowledgeBaseDocumentsParams,
        "function": list_knowledge_base_documents,
    }
