"""
Tool for exploring the web via Firecrawl.

Uses Firecrawl Search with content scraping (markdown) so the model can
retrieve fresh web context on demand.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ExploreWebParams(BaseModel):
    query: str = Field(description="Web search query to explore.")
    limit: int = Field(default=3, ge=1, le=10, description="Max results to return.")


class ExploreWebResultItem(BaseModel):
    url: str
    title: str | None = None
    description: str | None = None
    markdown: str | None = None


class ExploreWebResult(BaseModel):
    results: list[ExploreWebResultItem] = Field(default_factory=list)
    message: str = Field(default="Successfully explored the web")
    debug: dict | None = Field(
        default=None,
        description="Debug metadata about the Firecrawl response (for troubleshooting).",
    )


def _truncate(s: str | None, max_chars: int) -> str | None:
    if s is None:
        return None
    if len(s) <= max_chars:
        return s
    return s[:max_chars]


def _to_plain(obj):
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "to_dict"):
        try:
            return obj.to_dict()
        except Exception:
            pass
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            pass
    return obj


def _pick_results_list(resp_dict: dict) -> list | None:
    """
    Firecrawl search responses vary by SDK/version. Common shapes:
    - {"success": true, "data": [ ... ]}
    - {"success": true, "data": {"web": [ ... ]}}
    - {"web": [ ... ]}
    """
    data = resp_dict.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in ("web", "results", "data"):
            v = data.get(k)
            if isinstance(v, list):
                return v
    for k in ("web", "results"):
        v = resp_dict.get(k)
        if isinstance(v, list):
            return v
    return None


def _extract_url(item: dict) -> str:
    return (
        item.get("url")
        or item.get("link")
        or item.get("href")
        or (item.get("metadata") or {}).get("sourceURL")
        or (item.get("metadata") or {}).get("source_url")
        or ""
    )


def _extract_markdown(item: dict) -> str | None:
    md = item.get("markdown")
    if isinstance(md, str) and md.strip():
        return md
    # Some responses put scraped content under "content" or nested "data"
    c = item.get("content")
    if isinstance(c, str) and c.strip():
        return c
    return None


def _explore_web_impl(query: str, limit: int) -> ExploreWebResult:
    from django.conf import settings
    from firecrawl import Firecrawl

    api_key = getattr(settings, "FIRECRAWL_API_KEY", None)
    if not api_key:
        return ExploreWebResult(
            results=[],
            message="FIRECRAWL_API_KEY is not configured",
            debug={"configured": False},
        )

    firecrawl = Firecrawl(api_key=api_key)

    resp = None
    # Firecrawl SDK parameter naming differs between versions: scrapeOptions vs scrape_options.
    try:
        resp = firecrawl.search(
            query=query,
            limit=limit,
            scrapeOptions={"formats": ["markdown"], "onlyMainContent": True},
        )
    except TypeError:
        resp = firecrawl.search(
            query=query,
            limit=limit,
            scrape_options={"formats": ["markdown"], "onlyMainContent": True},
        )

    resp_plain = _to_plain(resp)
    resp_dict = resp_plain if isinstance(resp_plain, dict) else {"data": resp_plain}

    # Detect Firecrawl error responses explicitly (avoids silently returning []).
    if isinstance(resp_dict, dict) and resp_dict.get("success") is False:
        err = resp_dict.get("error") or resp_dict.get("message") or "Firecrawl search failed"
        logger.warning("Firecrawl search returned success=false: %s", err)
        return ExploreWebResult(
            results=[],
            message=str(err),
            debug={"success": False, "keys": sorted(list(resp_dict.keys()))[:50]},
        )

    web_results = _pick_results_list(resp_dict)

    items: list[ExploreWebResultItem] = []
    if isinstance(web_results, list):
        for r in web_results[:limit]:
            if not isinstance(r, dict):
                continue
            url = _extract_url(r)
            items.append(
                ExploreWebResultItem(
                    url=url,
                    title=r.get("title") or (r.get("metadata") or {}).get("title"),
                    description=(
                        r.get("description")
                        or r.get("snippet")
                        or (r.get("metadata") or {}).get("description")
                    ),
                    markdown=_truncate(_extract_markdown(r), 50_000),
                )
            )

    # Filter out any empty URLs
    items = [i for i in items if i.url]

    debug = {
        "success": resp_dict.get("success", True) if isinstance(resp_dict, dict) else True,
        "top_level_keys": sorted(list(resp_dict.keys()))[:50] if isinstance(resp_dict, dict) else [],
        "raw_results_type": type(web_results).__name__,
        "raw_results_count": len(web_results) if isinstance(web_results, list) else None,
        "parsed_results_count": len(items),
    }
    if not items:
        logger.warning(
            "Firecrawl search returned 0 parsed results (raw_results_type=%s raw_count=%s) query=%r",
            debug["raw_results_type"],
            debug["raw_results_count"],
            query,
        )

    return ExploreWebResult(results=items, debug=debug)


def get_tool(**kwargs) -> dict:
    def explore_web(query: str, limit: int = 3) -> ExploreWebResult:
        return _explore_web_impl(query=query, limit=limit)

    return {
        "name": "explore_web",
        "description": (
            "Search the web for up-to-date information using Firecrawl, returning URLs and scraped markdown. "
            "Use this when you need fresh web context."
        ),
        "parameters": ExploreWebParams,
        "function": explore_web,
    }

