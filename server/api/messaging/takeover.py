"""
Human takeover: staff temporarily replaces the AI agent on widget/WhatsApp threads.
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone
from pydantic import ValidationError as PydanticValidationError

from api.authenticate.services import FeatureFlagService
from api.notify.actions import notify_user

from .models import Conversation, ConversationTakeover, Message
from .schemas import ConversationTakeoverMetadata, takeover_metadata_payload

logger = logging.getLogger(__name__)

CAN_REPLACE_AGENT_IN_CONVERSATIONS_FLAG = "can-replace-agent-in-conversations"

TAKEOVER_EVENT_UPDATED = "conversation_takeover_updated"
TAKEOVER_EVENT_INBOUND = "conversation_takeover_inbound"
TAKEOVER_EVENT_MESSAGE_CREATED = "conversation_message_created"


def operator_display_name(user) -> str:
    full = (user.get_full_name() or "").strip()
    return full or user.username


def get_active_takeover(conversation: Conversation) -> ConversationTakeover | None:
    return (
        conversation.takeovers.filter(status=ConversationTakeover.Status.ACTIVE)
        .select_related("user")
        .first()
    )


def is_takeover_active(conversation: Conversation) -> bool:
    return conversation.takeovers.filter(
        status=ConversationTakeover.Status.ACTIVE
    ).exists()


def _resolve_organization_for_user(user, conversation: Conversation | None = None):
    from api.authenticate.models import Organization

    if conversation is not None and conversation.organization_id:
        return Organization.objects.filter(pk=conversation.organization_id).first()
    owned = Organization.objects.filter(owner=user).first()
    if owned:
        return owned
    if hasattr(user, "profile") and user.profile.organization_id:
        return Organization.objects.filter(pk=user.profile.organization_id).first()
    return None


def user_can_replace_agent(user, conversation: Conversation | None = None) -> bool:
    org = _resolve_organization_for_user(user, conversation)
    enabled, _ = FeatureFlagService.is_feature_enabled(
        CAN_REPLACE_AGENT_IN_CONVERSATIONS_FLAG,
        organization=org,
        user=user,
    )
    return enabled


def validate_takeover_metadata(raw: dict | None) -> dict:
    if not raw:
        return {}
    model = ConversationTakeoverMetadata.model_validate(raw)
    return model.model_dump(mode="json", exclude_none=True)


def _clear_whatsapp_inbound_buffer(conversation_id: str) -> None:
    from api.whatsapp.inbound import (
        whatsapp_inbound_buffer_key,
        whatsapp_inbound_schedule_lock_key,
    )

    cache.delete(whatsapp_inbound_buffer_key(conversation_id))
    cache.delete(whatsapp_inbound_schedule_lock_key(conversation_id))


def _emit_staff_event(user_id: int, event_type: str, payload: dict[str, Any]) -> None:
    notify_user(user_id, event_type, payload)


def emit_takeover_updated(
    conversation: Conversation,
    takeover: ConversationTakeover | None,
    *,
    action: str,
    operator_user_ids: list[int] | None = None,
) -> None:
    payload = {
        "conversation_id": str(conversation.id),
        "action": action,
        "takeover_id": str(takeover.id) if takeover else None,
        "status": takeover.status if takeover else None,
        "operator_user_id": takeover.user_id if takeover else None,
    }
    targets = operator_user_ids or []
    if takeover and takeover.user_id not in targets:
        targets.append(takeover.user_id)
    for uid in targets:
        _emit_staff_event(uid, TAKEOVER_EVENT_UPDATED, payload)


def emit_takeover_inbound(
    operator_user_id: int,
    conversation: Conversation,
    message: Message,
    takeover: ConversationTakeover,
) -> None:
    _emit_staff_event(
        operator_user_id,
        TAKEOVER_EVENT_INBOUND,
        {
            "conversation_id": str(conversation.id),
            "message_id": message.id,
            "takeover_id": str(takeover.id),
            "operator_user_id": operator_user_id,
        },
    )


def emit_message_created(
    user_ids: list[int],
    conversation: Conversation,
    message: Message,
) -> None:
    payload = {
        "conversation_id": str(conversation.id),
        "message_id": message.id,
    }
    for uid in user_ids:
        _emit_staff_event(uid, TAKEOVER_EVENT_MESSAGE_CREATED, payload)


def persist_inbound_from_user_inputs(
    conversation: Conversation,
    user_inputs: list[dict],
    *,
    message_metadata: dict | None = None,
) -> Message:
    from api.ai_layers.tasks import (
        _build_user_message_text,
        _resolve_user_inputs_and_attachments,
    )

    resolved_inputs, message_attachments, attachment_objects = (
        _resolve_user_inputs_and_attachments(
            user_inputs, conversation_id=str(conversation.id)
        )
    )
    text = _build_user_message_text(resolved_inputs)
    meta = dict(message_metadata or {})
    msg = Message.objects.create(
        conversation=conversation,
        type="user",
        text=text or ".",
        metadata=meta,
        attachments=message_attachments,
    )
    for att in attachment_objects:
        att.message = msg
        att.save(update_fields=["message"])
    return msg


def notify_widget_human_reply(conversation: Conversation, message: Message) -> None:
    if not conversation.widget_visitor_session_id:
        return
    route_id = f"widget_session:{conversation.widget_visitor_session_id}"
    notify_user(
        route_id,
        "agent_loop_finished",
        {
            "conversation_id": str(conversation.id),
            "output": message.text,
            "message_id": message.id,
            "versions": [
                {
                    "text": message.text,
                    "type": "assistant",
                    "agent_slug": "human",
                    "agent_name": "Support",
                }
            ],
            "iterations": 0,
            "tool_calls_count": 0,
        },
    )


def send_takeover_announcement(
    conversation: Conversation,
    takeover: ConversationTakeover,
    operator_name: str,
) -> Message | None:
    if takeover.announcement_sent_at:
        return None

    text = f"{operator_name} se unio a la conversacion para ayudarte."
    msg_metadata = {"human_takeover": True, "takeover_announcement": True}

    if conversation.ws_number_id and conversation.whatsapp_user_number:
        conversation.ws_number.send_message(conversation, text)
        msg = (
            conversation.messages.filter(type="assistant")
            .order_by("-id")
            .first()
        )
    elif conversation.widget_visitor_session_id:
        msg = Message.objects.create(
            conversation=conversation,
            type="assistant",
            text=text,
            metadata=msg_metadata,
        )
        notify_widget_human_reply(conversation, msg)
    else:
        msg = Message.objects.create(
            conversation=conversation,
            type="assistant",
            text=text,
            metadata=msg_metadata,
        )

    takeover.announcement_sent_at = timezone.now()
    takeover.save(update_fields=["announcement_sent_at"])
    return msg


@transaction.atomic
def start_takeover(conversation: Conversation, user) -> ConversationTakeover:
    existing = get_active_takeover(conversation)
    if existing:
        if existing.user_id == user.id:
            return existing
        raise ValueError("takeover_already_active")

    if conversation.ws_number_id:
        _clear_whatsapp_inbound_buffer(str(conversation.id))

    try:
        takeover = ConversationTakeover.objects.create(
            conversation=conversation,
            user=user,
            status=ConversationTakeover.Status.ACTIVE,
            metadata={},
        )
    except IntegrityError as exc:
        raise ValueError("takeover_already_active") from exc

    operator_name = operator_display_name(user)
    send_takeover_announcement(conversation, takeover, operator_name)
    emit_takeover_updated(
        conversation,
        takeover,
        action="started",
        operator_user_ids=[user.id],
    )
    return takeover


@transaction.atomic
def release_takeover(
    takeover: ConversationTakeover,
    *,
    ended_reason: str = "manual_release",
) -> ConversationTakeover:
    if takeover.status != ConversationTakeover.Status.ACTIVE:
        return takeover

    meta = validate_takeover_metadata(takeover.metadata or {})
    meta["ended_reason"] = ended_reason
    takeover.metadata = meta
    takeover.status = ConversationTakeover.Status.INACTIVE
    takeover.ended_at = timezone.now()
    takeover.save(update_fields=["status", "ended_at", "metadata"])
    # Re-enable agent runs after takeover release.
    cache.delete(f"cancel_task_{takeover.conversation_id}")

    emit_takeover_updated(
        takeover.conversation,
        takeover,
        action="released",
        operator_user_ids=[takeover.user_id],
    )
    return takeover


def deliver_human_message(
    conversation: Conversation,
    takeover: ConversationTakeover,
    text: str,
) -> Message:
    text = (text or "").strip()
    if not text:
        raise ValueError("message_required")

    msg_metadata = {
        "human_takeover": True,
        "takeover_id": str(takeover.id),
        "staff_user_id": takeover.user_id,
    }

    if conversation.ws_number_id and conversation.whatsapp_user_number:
        conversation.ws_number.send_message(conversation, text)
        msg = (
            conversation.messages.filter(type="assistant")
            .order_by("-id")
            .first()
        )
        if msg:
            merged = dict(msg.metadata or {})
            merged.update(msg_metadata)
            msg.metadata = merged
            msg.save(update_fields=["metadata"])
    elif conversation.widget_visitor_session_id:
        msg = Message.objects.create(
            conversation=conversation,
            type="assistant",
            text=text,
            metadata=msg_metadata,
        )
        notify_widget_human_reply(conversation, msg)
    else:
        msg = Message.objects.create(
            conversation=conversation,
            type="assistant",
            text=text,
            metadata=msg_metadata,
        )

    emit_message_created([takeover.user_id], conversation, msg)
    return msg


def handle_inbound_during_takeover(
    conversation: Conversation,
    takeover: ConversationTakeover,
    user_inputs: list[dict],
    *,
    message_metadata: dict | None = None,
) -> Message:
    msg = persist_inbound_from_user_inputs(
        conversation,
        user_inputs,
        message_metadata=message_metadata,
    )
    emit_takeover_inbound(takeover.user_id, conversation, msg, takeover)
    return msg
