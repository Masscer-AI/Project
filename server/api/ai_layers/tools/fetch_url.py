from __future__ import annotations

import logging
from urllib.parse import urlparse

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_MAX_MARKDOWN = 50_000


class FetchUrlParams(BaseModel):
    url: str = Field(description="HTTP or HTTPS URL to fetch as markdown.")


class FetchUrlResult(BaseModel):
    url: str
    markdown: str | None = None
    message: str = ""


def is_http_url(url: str) -> bool:
    parsed = urlparse((url or "").strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _markdown_from_scrape(scrape) -> str | None:
    if scrape is None:
        return None
    if isinstance(scrape, dict):
        md = scrape.get("markdown") or (scrape.get("data") or {}).get("markdown")
        if isinstance(md, str) and md.strip():
            return md
        return None
    md = getattr(scrape, "markdown", None)
    if isinstance(md, str) and md.strip():
        return md
    return None


def fetch_url_impl(url: str) -> FetchUrlResult:
    from django.conf import settings
    from firecrawl import Firecrawl

    raw = (url or "").strip()
    if not is_http_url(raw):
        return FetchUrlResult(url=raw, message="url must be http or https")
    api_key = getattr(settings, "FIRECRAWL_API_KEY", None)
    if not api_key:
        return FetchUrlResult(url=raw, message="FIRECRAWL_API_KEY is not configured")
    try:
        firecrawl = Firecrawl(api_key=api_key)
        scrape = firecrawl.scrape(raw, formats=["markdown"])
    except Exception as exc:
        logger.warning("fetch_url scrape failed url=%s err=%s", raw, exc)
        return FetchUrlResult(url=raw, message="could not fetch url")
    markdown = _markdown_from_scrape(scrape)
    if not markdown:
        return FetchUrlResult(url=raw, message="no content found")
    if len(markdown) > _MAX_MARKDOWN:
        markdown = markdown[:_MAX_MARKDOWN]
    return FetchUrlResult(url=raw, markdown=markdown, message="ok")


def get_tool(**kwargs) -> dict:
    def fetch_url(url: str) -> FetchUrlResult:
        return fetch_url_impl(url)

    return {
        "name": "fetch_url",
        "description": (
            "Fetch a web page by URL and return its main content as markdown. "
            "Use when you already have a specific URL to read."
        ),
        "parameters": FetchUrlParams,
        "function": fetch_url,
    }
