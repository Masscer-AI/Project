"""
List predefined Masscer help topics (ids + summaries) for the platform assistant.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from api.ai_layers.masscer_help import HelpTopicListItem, load_help_topic_catalog


class ListMasscerHelpTopicsParams(BaseModel):
    pass


class ListMasscerHelpTopicsResult(BaseModel):
    topics: list[HelpTopicListItem] = Field(default_factory=list)
    message: str = "Successfully listed Masscer help topics"


def _list_masscer_help_topics_impl() -> ListMasscerHelpTopicsResult:
    catalog = load_help_topic_catalog()
    items = [
        HelpTopicListItem(
            id=t.id,
            title=t.title,
            summary=t.summary,
            keywords=t.keywords,
        )
        for t in catalog.topics
    ]
    return ListMasscerHelpTopicsResult(topics=items)


def get_tool(**kwargs) -> dict:
    def list_masscer_help_topics() -> ListMasscerHelpTopicsResult:
        return _list_masscer_help_topics_impl()

    return {
        "name": "list_masscer_help_topics",
        "description": (
            "List all predefined Masscer help topics (id, title, summary, keywords). "
            "Use before get_masscer_help_topic when you need to pick the right topic_id."
        ),
        "parameters": ListMasscerHelpTopicsParams,
        "function": list_masscer_help_topics,
    }
