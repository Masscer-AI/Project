"""Shared rules for widget and WhatsApp agent tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api.messaging.models import Conversation


def conversation_uses_capability_gated_media_tools(conversation: Conversation) -> bool:
    """
    Widget and WhatsApp threads gate image/speech via line/widget capabilities only.

    App chat still requires org/user feature flags (image-tools, chat-generate-speech).
    """
    return bool(conversation.chat_widget_id or conversation.ws_number_id)
