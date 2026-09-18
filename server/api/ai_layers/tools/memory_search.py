"""
Tool: memory_search

Semantic search over the current agent's trained memory (approved completions).
"""

from __future__ import annotations

import logging

from django.db.models import Q
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MemorySearchParams(BaseModel):
    queries: list[str] = Field(
        description="List of search queries to run against the agent's trained memory."
    )
    n_results: int = Field(
        default=4,
        ge=1,
        le=20,
        description="Number of results to retrieve per query.",
    )


class MemorySearchResult(BaseModel):
    queries_used: list[str] = Field(default_factory=list)
    results: dict = Field(
        default_factory=dict,
        description="Raw vector store query results",
    )
    message: str = Field(default="Successfully searched agent memory")


def _memory_search_impl(
    *,
    user_id: int,
    agent_slug: str,
    queries: list[str],
    n_results: int,
) -> MemorySearchResult:
    from django.contrib.auth.models import User

    from api.ai_layers.models import Agent
    from api.rag.managers import chroma_client
    from api.rag.models import Collection

    if not chroma_client:
        raise ValueError("ChromaDB is not available")

    if not queries or not isinstance(queries, list):
        raise ValueError("queries must be a non-empty list of strings")

    cleaned = [q.strip() for q in queries if isinstance(q, str) and q.strip()]
    if not cleaned:
        raise ValueError("queries must contain at least one non-empty string")

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        raise ValueError("User not found")

    from api.ai_layers.access import accessible_agents_qs

    agent = Agent.objects.filter(slug=agent_slug).filter(
        Q(is_public=True) | Q(id__in=accessible_agents_qs(user).values_list("id", flat=True))
    ).first()
    if not agent:
        raise ValueError("Agent not found or user is not allowed to access it")

    collection, created = Collection.get_or_create_agent_collection(agent=agent)
    if created:
        return MemorySearchResult(
            queries_used=cleaned,
            results={},
            message="No collection found; created new one",
        )

    try:
        results = chroma_client.get_results(
            collection_name=collection.slug,
            query_texts=cleaned,
            n_results=n_results,
        )
    except Exception as exc:
        logger.exception(
            "memory_search failed for agent_slug=%s collection=%s user_id=%s queries=%s",
            agent_slug,
            collection.slug,
            user_id,
            cleaned,
        )
        raise ValueError(f"memory_search failed: {str(exc)}") from exc

    return MemorySearchResult(queries_used=cleaned, results={"results": results})


def get_tool(
    user_id: int | None = None,
    agent_slug: str | None = None,
    **kwargs,
) -> dict:
    """
    Tool config. Requires user_id and agent_slug via closure.
    For widget conversations (user_id=None), falls back to the agent owner for auth context.
    """
    if not agent_slug:
        raise ValueError("memory_search requires agent_slug in tool context")
    if user_id is None:
        from api.ai_layers.models import Agent

        try:
            agent = Agent.objects.get(slug=agent_slug)
            user_id = agent.user_id
        except Agent.DoesNotExist:
            raise ValueError("memory_search: agent not found")
        if user_id is None:
            raise ValueError(
                "memory_search requires user_id in tool context (agent has no owner)"
            )

    def memory_search(queries: list[str], n_results: int = 4) -> MemorySearchResult:
        return _memory_search_impl(
            user_id=user_id,
            agent_slug=agent_slug,
            queries=queries,
            n_results=n_results,
        )

    return {
        "name": "memory_search",
        "description": (
            "Semantic search over the current agent's trained memory "
            "(approved completions in the agent vector store). "
            "Not a catalog of uploaded knowledge-base documents — "
            "use list_knowledge_base_documents / read_knowledge_base_document for those. "
            "Pass 1-5 queries derived from the user's request."
        ),
        "parameters": MemorySearchParams,
        "function": memory_search,
    }
