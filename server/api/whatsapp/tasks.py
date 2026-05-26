import logging

from celery import shared_task
from django.core.cache import cache

from .actions import deliver_whatsapp_reply, handle_webhook, send_whatsapp_fallback_text

logger = logging.getLogger(__name__)


@shared_task
def async_handle_webhook(webhook_data):
    result = handle_webhook(webhook_data=webhook_data)
    return result


@shared_task
def whatsapp_flush_inbound_agent_task(
    *,
    conversation_id: str,
    ws_number_id: int,
    whatsapp_user_number: str,
):
    from .inbound import (
        whatsapp_inbound_buffer_key,
        whatsapp_inbound_schedule_lock_key,
    )

    buffer_key = whatsapp_inbound_buffer_key(conversation_id)
    schedule_lock_key = whatsapp_inbound_schedule_lock_key(conversation_id)

    buffered_payloads = cache.get(buffer_key) or []
    cache.delete(buffer_key)
    cache.delete(schedule_lock_key)

    if not buffered_payloads:
        return {"status": "skipped", "reason": "empty_buffer"}

    merged_user_inputs: list[dict] = []
    regenerate_ids: list[int] = []
    latest_inbound_wamid: str | None = None

    for payload in buffered_payloads:
        merged_user_inputs.extend(payload.get("user_inputs") or [])
        regenerate_id = payload.get("regenerate_message_id")
        if isinstance(regenerate_id, int):
            regenerate_ids.append(regenerate_id)
        wamid = payload.get("inbound_wamid")
        if isinstance(wamid, str) and wamid:
            latest_inbound_wamid = wamid

    if not merged_user_inputs:
        return {"status": "skipped", "reason": "empty_user_inputs"}

    from api.messaging.models import Conversation
    from api.messaging.takeover import is_takeover_active

    try:
        conv = Conversation.objects.get(id=conversation_id)
    except Conversation.DoesNotExist:
        return {"status": "skipped", "reason": "conversation_not_found"}
    if is_takeover_active(conv):
        return {"status": "skipped", "reason": "takeover_active"}

    regenerate_message_id = min(regenerate_ids) if regenerate_ids else None
    return whatsapp_conversation_agent_task(
        conversation_id=conversation_id,
        user_inputs=merged_user_inputs,
        ws_number_id=ws_number_id,
        whatsapp_user_number=whatsapp_user_number,
        inbound_wamid=latest_inbound_wamid,
        regenerate_message_id=regenerate_message_id,
    )


@shared_task
def whatsapp_conversation_agent_task(
    *,
    conversation_id: str,
    user_inputs: list[dict],
    ws_number_id: int,
    whatsapp_user_number: str,
    inbound_wamid: str | None = None,
    regenerate_message_id: int | None = None,
):
    """
    Run conversation_agent_task for a WhatsApp thread, then deliver via Graph API.
    """
    from api.ai_layers.tasks import conversation_agent_task
    from api.messaging.models import Conversation
    from api.messaging.schemas import metadata_payload_for_related_agents

    from .conversations import tool_names_from_capabilities

    try:
        conv = Conversation.objects.select_related(
            "ws_number",
            "ws_number__agent",
        ).get(id=conversation_id)
    except Conversation.DoesNotExist:
        return {"status": "error", "error": "Conversation not found"}

    if not conv.ws_number_id or conv.ws_number_id != ws_number_id:
        return {"status": "error", "error": "Conversation does not belong to ws_number"}
    if conv.whatsapp_user_number != whatsapp_user_number:
        return {"status": "error", "error": "WhatsApp user mismatch"}

    from api.messaging.takeover import is_takeover_active

    if is_takeover_active(conv):
        return {"status": "skipped", "reason": "takeover_active"}

    ws_number = conv.ws_number
    tool_names = tool_names_from_capabilities(ws_number.capabilities)

    conv.metadata = metadata_payload_for_related_agents([ws_number.agent_id])
    conv.save(update_fields=["metadata", "updated_at"])

    # Anonymous like widgets: string route so actor_user_id stays unset (no UserProfile in prompt).
    route_key = f"whatsapp:{conv.id}"

    result = conversation_agent_task(
        conversation_id=str(conv.id),
        user_inputs=user_inputs,
        tool_names=tool_names,
        agent_slugs=[ws_number.agent.slug],
        multiagentic_modality="isolated",
        user_id=route_key,
        regenerate_message_id=regenerate_message_id,
        client_datetime=None,
    )

    if not isinstance(result, dict):
        logger.warning(
            "whatsapp_conversation_agent_task: unexpected non-dict result; skipping delivery. "
            "conversation_id=%s result=%r",
            conversation_id,
            result,
        )
        return {"status": "skipped", "reason": "invalid_result"}

    if result.get("status") == "completed" and result.get("message_id"):
        try:
            deliver_whatsapp_reply(
                conversation=conv,
                assistant_message_id=result["message_id"],
                inbound_wamid=inbound_wamid,
            )
        except Exception:
            logger.exception(
                "deliver_whatsapp_reply failed conversation_id=%s assistant_id=%s",
                conversation_id,
                result.get("message_id"),
            )
    elif result.get("status") == "cancelled":
        logger.info(
            "whatsapp_conversation_agent_task: cancelled conversation_id=%s",
            conversation_id,
        )
    else:
        logger.warning(
            "whatsapp_conversation_agent_task: agent task did not complete; sending fallback. "
            "conversation_id=%s result=%s",
            conversation_id,
            result,
        )
        try:
            send_whatsapp_fallback_text(conv, inbound_wamid=inbound_wamid)
        except Exception:
            logger.exception(
                "send_whatsapp_fallback_text failed conversation_id=%s",
                conversation_id,
            )

    return result
