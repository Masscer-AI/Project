"""Shared rules for widget and WhatsApp agent tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api.messaging.models import Conversation


def organization_can_access_conversation(
    *,
    conv: "Conversation",
    organization_id,
) -> bool:
    """Same org visibility as dashboard scope=org (incl. app chats with null organization_id)."""
    if conv.status == "deleted":
        return False
    from api.messaging.models import Conversation
    from api.messaging.views import organization_conversations_q

    return Conversation.objects.filter(
        organization_conversations_q(organization_id),
        pk=conv.pk,
    ).exists()


def conversation_uses_capability_gated_media_tools(conversation: Conversation) -> bool:
    """
    Widget and WhatsApp threads gate image/speech via line/widget capabilities only.

    App chat still requires org/user feature flags (image-tools, chat-generate-speech).
    """
    return bool(conversation.chat_widget_id or conversation.ws_number_id)
