"""
Shared conversation visibility for agent tools (web chat + linked WhatsApp).

Rule: SAME USER, SAME conversations access.
WhatsApp threads stay Conversation.user=None; access is via WSContact.user.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Q

from api.messaging.organization_scope import organization_conversations_q

if TYPE_CHECKING:
    from api.messaging.models import Conversation


def user_owned_conversations_q(
    user_id: int,
    organization_id: int | None = None,
) -> Q:
    """
    Conversations owned by the user or WhatsApp threads linked via WSContact.user.

    Org filter matches existing get_tag_context user scope: same org or null org.
    """
    q = Q(user_id=user_id) | Q(ws_contact__user_id=user_id)
    if organization_id is not None:
        q &= Q(organization_id=organization_id) | Q(organization_id__isnull=True)
    return q


def user_accessible_conversations_q(
    *,
    user_id: int,
    organization_id: int,
    has_organization_conversations_access: bool = False,
) -> Q:
    """Visibility for list/tag/query tools for a logged-in (or linked) actor."""
    if has_organization_conversations_access:
        return organization_conversations_q(organization_id)
    return user_owned_conversations_q(user_id, organization_id)


def user_can_access_conversation(
    *,
    conv: "Conversation",
    user_id: int,
    organization_id: int,
    has_organization_conversations_access: bool = False,
) -> bool:
    """Whether the actor may inspect this conversation via agent tools."""
    if conv.status == "deleted":
        return False
    from api.messaging.models import Conversation

    return Conversation.objects.filter(
        user_accessible_conversations_q(
            user_id=user_id,
            organization_id=organization_id,
            has_organization_conversations_access=has_organization_conversations_access,
        ),
        pk=conv.pk,
    ).exists()


def conversation_channel(conv: "Conversation") -> str:
    if conv.ws_number_id is not None:
        return "whatsapp"
    if conv.chat_widget_id is not None:
        return "widget"
    return "web"
