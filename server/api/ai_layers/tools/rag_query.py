"""
Tool for querying the vector store (RAG) for the current agent.

The agent supplies the list of queries; this tool just runs retrieval and returns results.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RagQueryParams(BaseModel):
    queries: list[str] = Field(
        description="List of search queries to run against the vector store."
    )
    n_results: int = Field(
        default=4,
        ge=1,
        le=20,
        description="Number of results to retrieve per query.",
    )


class RagQueryResult(BaseModel):
    queries_used: list[str] = Field(default_factory=list)
    results: dict = Field(default_factory=dict, description="Raw vector store query results")
    message: str = Field(default="Successfully queried RAG")


def _rag_query_impl(
    *,
    user_id: int,
    agent_slug: str,
    queries: list[str],
    n_results: int,
) -> RagQueryResult:
    from django.contrib.auth.models import User
    from api.ai_layers.models import Agent
    from api.rag.models import Collection
    from api.rag.managers import chroma_client

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

    try:
        agent = Agent.objects.get(slug=agent_slug)
    except Agent.DoesNotExist:
        raise ValueError("Agent not found")

    collection, created = Collection.objects.get_or_create(user=user, agent=agent)
    if created:
        # No data yet; return empty results.
        return RagQueryResult(queries_used=cleaned, results={}, message="No collection found; created new one")

    results = chroma_client.get_results(
        collection_name=collection.slug,
        query_texts=cleaned,
        n_results=n_results,
    )

    return RagQueryResult(queries_used=cleaned, results={"results": results})


def get_tool(
    user_id: int | None = None,
    agent_slug: str | None = None,
    **kwargs,
) -> dict:
    """
    Tool config. Requires user_id and agent_slug via closure.
    For widget conversations (user_id=None), falls back to the agent owner's collection.
    """
    if not agent_slug:
        raise ValueError("rag_query requires agent_slug in tool context")
    # Widget context: use agent owner's RAG collection
    if user_id is None:
        from api.ai_layers.models import Agent

        try:
            agent = Agent.objects.get(slug=agent_slug)
            user_id = agent.user_id
        except Agent.DoesNotExist:
            raise ValueError("rag_query: agent not found")
        if user_id is None:
            raise ValueError("rag_query requires user_id in tool context (agent has no owner)")

    def rag_query(queries: list[str], n_results: int = 4) -> RagQueryResult:
        return _rag_query_impl(
            user_id=user_id,
            agent_slug=agent_slug,
            queries=queries,
            n_results=n_results,
        )

    return {
        "name": "rag_query",
        "description": (
            "Query the vector store for the current agent using the provided list of queries. "
            "Returns relevant chunks/metadata to help answer the user's question."
        ),
        "parameters": RagQueryParams,
        "function": rag_query,
    }

