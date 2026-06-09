"""
Return predefined Masscer product help for a topic id (onboarding / how-to).
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from api.ai_layers.masscer_help import HelpTopicDetail, load_help_topic_catalog

logger = logging.getLogger(__name__)


class GetMasscerHelpTopicParams(BaseModel):
    topic_id: str = Field(
        description=(
            "Help topic id, e.g. invite_user, manage_roles, create_agent. "
            "Use list_masscer_help_topics to see all ids."
        )
    )


def _get_masscer_help_topic_impl(
    topic_id: str,
    *,
    user_id: int | None = None,
    organization_id=None,
) -> HelpTopicDetail:
    catalog = load_help_topic_catalog()
    topic = catalog.by_id(topic_id.strip())
    if not topic:
        available = ", ".join(t.id for t in catalog.topics)
        raise ValueError(
            f"Unknown topic_id '{topic_id}'. Available topics: {available}"
        )

    access_allowed = True
    access_message = None
    if topic.required_flag and user_id:
        from django.contrib.auth.models import User

        from api.authenticate.models import Organization
        from api.authenticate.services import FeatureFlagService

        org = None
        if organization_id:
            org = Organization.objects.filter(id=organization_id).first()
        user = User.objects.filter(pk=user_id).first()
        enabled, reason = FeatureFlagService.is_feature_enabled(
            topic.required_flag,
            organization=org,
            user=user,
        )
        if not enabled:
            access_allowed = False
            access_message = (
                f"This topic requires the '{topic.required_flag}' permission "
                f"(reason: {reason}). Tell the user they may need their org admin "
                f"to grant access."
            )

    return HelpTopicDetail(
        id=topic.id,
        title=topic.title,
        summary=topic.summary,
        steps=topic.steps,
        app_url=topic.build_app_url(),
        required_flag=topic.required_flag,
        access_allowed=access_allowed,
        access_message=access_message,
    )


def get_tool(
    user_id: int | None = None,
    organization_id=None,
    **kwargs,
) -> dict:
    def get_masscer_help_topic(topic_id: str) -> HelpTopicDetail:
        return _get_masscer_help_topic_impl(
            topic_id,
            user_id=user_id,
            organization_id=organization_id,
        )

    return {
        "name": "get_masscer_help_topic",
        "description": (
            "Get step-by-step Masscer product help for a predefined topic. "
            "Returns title, summary, ordered steps, and app_url (frontend path) "
            "the user should open. Call this when the user asks how to do something "
            "in Masscer (invite users, roles, agents, billing, etc.). "
            "Use list_masscer_help_topics first if unsure of the topic_id."
        ),
        "parameters": GetMasscerHelpTopicParams,
        "function": get_masscer_help_topic,
    }
