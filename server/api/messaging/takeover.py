"""
Human takeover: staff temporarily replaces the AI agent on widget/WhatsApp threads.
"""

from __future__ import annotations

import logging
from typing import Any

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone
from pydantic import ValidationError as PydanticValidationError

from api.authenticate.models import Organization
from api.authenticate.services import FeatureFlagService
from api.notify.actions import notify_user

from .models import Conversation, ConversationTakeover, Message, MessageAttachment
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


def get_conversation_staff_user_ids(conversation: Conversation) -> list[int]:
    """
    Best-effort set of internal users that can care about conversation updates.
    Used for realtime refresh events on read-only viewers.
    """
    user_ids: set[int] = set()

    if conversation.user_id:
        user_ids.add(conversation.user_id)

    org_ids: set[str] = set()
    if conversation.organization_id:
        org_ids.add(str(conversation.organization_id))
    if conversation.ws_number_id and conversation.ws_number.organization_id:
        org_ids.add(str(conversation.ws_number.organization_id))

    if org_ids:
        orgs = Organization.objects.filter(id__in=org_ids)
        user_ids.update(orgs.values_list("owner_id", flat=True))
        member_ids = User.objects.filter(
            profile__organization_id__in=org_ids
        ).values_list("id", flat=True)
        user_ids.update(member_ids)

    if conversation.chat_widget_id and conversation.chat_widget.created_by_id:
        user_ids.add(conversation.chat_widget.created_by_id)
    if conversation.ws_number_id and conversation.ws_number.user_id:
        user_ids.add(conversation.ws_number.user_id)

    return [uid for uid in user_ids if isinstance(uid, int)]


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
    targets = set(operator_user_ids or [])
    targets.update(get_conversation_staff_user_ids(conversation))
    if takeover and takeover.user_id not in targets:
        targets.add(takeover.user_id)
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
    user_ids: list[int] | None,
    conversation: Conversation,
    message: Message,
) -> None:
    payload = {
        "conversation_id": str(conversation.id),
        "message_id": message.id,
    }
    targets = set(user_ids or [])
    targets.update(get_conversation_staff_user_ids(conversation))
    for uid in targets:
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
        conversation.ws_number.send_message(
            conversation,
            text,
            reply_to_last_inbound=False,
        )
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
    *,
    attachment_ids: list[str] | None = None,
) -> Message:
    text = (text or "").strip()
    attachment_ids = [str(aid) for aid in (attachment_ids or []) if str(aid).strip()]
    if not text and not attachment_ids:
        raise ValueError("message_required")

    msg_metadata = {
        "human_takeover": True,
        "takeover_id": str(takeover.id),
        "staff_user_id": takeover.user_id,
    }

    from api.ai_layers.tasks import _resolve_user_inputs_and_attachments

    user_inputs: list[dict] = []
    if text:
        user_inputs.append({"type": "input_text", "text": text})
    for aid in attachment_ids:
        user_inputs.append({"type": "input_attachment", "attachment_id": aid})

    _resolved_inputs, message_attachments, attachment_objects = (
        _resolve_user_inputs_and_attachments(
            user_inputs,
            conversation_id=str(conversation.id),
        )
    )

    if conversation.ws_number_id and conversation.whatsapp_user_number:
        normalized_attachments: list[MessageAttachment] = []
        for att in attachment_objects:
            if att.kind == "file":
                normalized_attachments.append(att)
                continue
            if att.kind == "rag_document" and att.rag_document_id:
                doc = att.rag_document
                file_field = getattr(doc, "file", None) if doc else None
                if file_field:
                    cloned = MessageAttachment.objects.create(
                        conversation=conversation,
                        user=takeover.user,
                        kind="file",
                        file=file_field,
                        content_type=getattr(doc, "content_type", "") or "",
                    )
                    normalized_attachments.append(cloned)
        if normalized_attachments:
            attachment_objects = normalized_attachments
            from api.ai_layers.tasks import _message_attachment_to_display_dict

            message_attachments = [
                d
                for d in (
                    _message_attachment_to_display_dict(att)
                    for att in attachment_objects
                )
                if d is not None
            ]
        elif not text:
            raise ValueError("message_required")

    msg = Message.objects.create(
        conversation=conversation,
        type="assistant",
        text=text,
        metadata=msg_metadata,
        attachments=message_attachments,
    )
    if attachment_objects:
        MessageAttachment.objects.filter(
            id__in=[att.id for att in attachment_objects]
        ).update(message=msg)

    if conversation.ws_number_id and conversation.whatsapp_user_number:
        from api.whatsapp.actions import send_message as send_text_message
        from api.whatsapp.outbound_media import deliver_whatsapp_attachments

        media_wamids = []
        if attachment_objects:
            media_wamids = deliver_whatsapp_attachments(
                phone_number_id=conversation.ws_number.platform_id,
                to=conversation.whatsapp_user_number,
                assistant_message=msg,
                reply_to_message_id=None,
            )

        text_wamid = None
        if text:
            text_wamid = send_text_message(
                conversation.ws_number.platform_id,
                conversation.whatsapp_user_number,
                text,
                None,
            )

        merged = dict(msg.metadata or {})
        if media_wamids:
            merged["whatsapp_media_wamids"] = media_wamids
        if text_wamid:
            merged["whatsapp_wamid"] = text_wamid
        msg.metadata = merged
        msg.save(update_fields=["metadata"])
    elif conversation.widget_visitor_session_id:
        notify_widget_human_reply(conversation, msg)

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
    emit_message_created(None, conversation, msg)
    emit_takeover_inbound(takeover.user_id, conversation, msg, takeover)
    return msg
