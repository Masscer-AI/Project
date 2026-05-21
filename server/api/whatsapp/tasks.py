import logging

from celery import shared_task

from .actions import deliver_whatsapp_reply, handle_webhook, send_whatsapp_fallback_text

logger = logging.getLogger(__name__)


@shared_task
def async_handle_webhook(webhook_data):
    result = handle_webhook(webhook_data=webhook_data)
    return result


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
