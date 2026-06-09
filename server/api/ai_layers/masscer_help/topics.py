"""
Pydantic models and loader for Masscer Assistant help topics.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlencode

from pydantic import BaseModel, Field, field_validator

_HELP_TOPICS_JSON = Path(__file__).with_name("help_topics.json")


class HelpTopicStep(BaseModel):
    order: int = Field(ge=1)
    text: str = Field(min_length=1)


class HelpTopic(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    steps: list[HelpTopicStep] = Field(min_length=1)
    app_path: str = Field(pattern=r"^/")
    query_params: dict[str, str] | None = None
    keywords: list[str] = Field(default_factory=list)
    required_flag: str | None = None

    @field_validator("steps")
    @classmethod
    def steps_sorted_unique_order(cls, v: list[HelpTopicStep]) -> list[HelpTopicStep]:
        orders = [s.order for s in v]
        if len(orders) != len(set(orders)):
            raise ValueError("step order values must be unique")
        return sorted(v, key=lambda s: s.order)

    def build_app_url(self) -> str:
        if not self.query_params:
            return self.app_path
        return f"{self.app_path}?{urlencode(self.query_params)}"


class HelpTopicCatalog(BaseModel):
    version: int = Field(ge=1)
    topics: list[HelpTopic] = Field(min_length=1)

    @field_validator("topics")
    @classmethod
    def unique_topic_ids(cls, v: list[HelpTopic]) -> list[HelpTopic]:
        ids = [t.id for t in v]
        if len(ids) != len(set(ids)):
            raise ValueError("topic ids must be unique")
        return v

    def by_id(self, topic_id: str) -> HelpTopic | None:
        return next((t for t in self.topics if t.id == topic_id), None)


class HelpTopicListItem(BaseModel):
    id: str
    title: str
    summary: str
    keywords: list[str]


class HelpTopicDetail(BaseModel):
    id: str
    title: str
    summary: str
    steps: list[HelpTopicStep]
    app_url: str
    required_flag: str | None = None
    access_allowed: bool = True
    access_message: str | None = None


@lru_cache(maxsize=1)
def load_help_topic_catalog() -> HelpTopicCatalog:
    raw = json.loads(_HELP_TOPICS_JSON.read_text(encoding="utf-8"))
    return HelpTopicCatalog.model_validate(raw)


def reload_help_topic_catalog_for_tests() -> None:
    """Clear cached catalog (tests only)."""
    load_help_topic_catalog.cache_clear()
