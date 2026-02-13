import logging
from celery import shared_task
from .actions import generate_agent_profile_picture

logger = logging.getLogger(__name__)


@shared_task
def async_generate_agent_profile_picture(agent_id: int):
    result = generate_agent_profile_picture(agent_id)
    return result


def _build_user_message_text(user_inputs: list[dict]) -> str:
    """
    Build a plain-text user message from user_inputs.

    Currently concatenates all input_text entries. In the future this can
    handle input_image, input_document, etc. by building richer prompts.
    """
    parts = []
    for inp in user_inputs:
        input_type = inp.get("type", "")
        if input_type == "input_text":
            text = inp.get("text", "").strip()
            if text:
                parts.append(text)
        # Future: input_image, input_document, etc.
    return "\n".join(parts)


@shared_task
def conversation_agent_task(
    conversation_id: str,
    user_inputs: list[dict],
    tool_names: list[str],
    instructions: str,
    user_id: int,
    model: str = "gpt-4o",
):
    """
    Celery task that runs an AgentLoop for a conversation.

    Resolves tools from the registry, executes the agent loop, and emits
    real-time status updates via Redis pub/sub (notify_user) so the frontend
    can show progress to the user. Messages are always saved.

    Args:
        conversation_id: UUID of the conversation
        user_inputs: list of input dicts, e.g. [{"type": "input_text", "text": "..."}]
        tool_names: list of tool names to resolve from the registry
        instructions: system prompt / instructions (derived from Agent model)
        user_id: ID of the user (for notifications)
        model: LLM model slug (derived from Agent model)

    Returns:
        dict with status, output, iterations, and tool_calls count
    """
    from api.ai_layers.agent_loop import AgentLoop
    from api.ai_layers.tools import resolve_tools
    from api.notify.actions import notify_user
    from api.messaging.models import Conversation, Message

    # Build plain-text message from user_inputs
    user_message = _build_user_message_text(user_inputs)

    logger.info(
        "conversation_agent_task started: conversation=%s user=%s tools=%s model=%s",
        conversation_id, user_id, tool_names, model,
    )

    # ---- Two-channel notification system ----
    # 1. agent_events_channel: intermediate events (tool calls, errors, progress)
    #    payload: { type: str, conversation_id: str, ...event-specific keys }
    # 2. agent_loop_finished: final event with the response
    #    payload: { conversation_id: str, output: str, message_id: int|None, ... }

    def emit_event(event_type: str, data: dict) -> None:
        """Push an intermediate event to agent_events_channel."""
        payload = {"type": event_type, "conversation_id": conversation_id, **data}
        notify_user(user_id, "agent_events_channel", payload)

    def emit_finished(data: dict) -> None:
        """Push the final agent_loop_finished event."""
        payload = {"conversation_id": conversation_id, **data}
        notify_user(user_id, "agent_loop_finished", payload)

    def on_event(event_type: str, data: dict) -> None:
        """Route AgentLoop events to the two-channel system."""
        emit_event(event_type, data)

    try:
        # ---- Resolve tools ----
        tools = resolve_tools(tool_names) if tool_names else []

        # ---- Save user message ----
        try:
            conversation = Conversation.objects.get(id=conversation_id)
            Message.objects.create(
                conversation=conversation,
                type="user",
                text=user_message,
            )
        except Conversation.DoesNotExist:
            logger.error("Conversation %s not found", conversation_id)
            emit_event("error", {"error": f"Conversation {conversation_id} not found"})
            return {"status": "error", "error": "Conversation not found"}

        # ---- Run the agent loop ----
        loop = AgentLoop(
            tools=tools,
            instructions=instructions,
            model=model,
            on_event=on_event,
        )
        result = loop.run(user_message)

        # ---- Extract output text ----
        import json as _json
        if isinstance(result.output, str):
            output_text = result.output
        elif hasattr(result.output, "model_dump"):
            output_text = _json.dumps(result.output.model_dump(), default=str)
        else:
            output_text = str(result.output)

        # ---- Save assistant message ----
        assistant_message_id = None
        try:
            conversation = Conversation.objects.get(id=conversation_id)
            assistant_msg = Message.objects.create(
                conversation=conversation,
                type="assistant",
                text=output_text,
            )
            assistant_message_id = assistant_msg.id

            # Generate title if conversation doesn't have one
            conversation.generate_title()
        except Conversation.DoesNotExist:
            logger.warning(
                "Conversation %s not found when saving assistant message",
                conversation_id,
            )

        # ---- Emit final event ----
        emit_finished({
            "output": output_text,
            "message_id": assistant_message_id,
            "iterations": result.iterations,
            "tool_calls_count": len(result.tool_calls),
        })

        logger.info(
            "conversation_agent_task completed: conversation=%s iterations=%d tool_calls=%d",
            conversation_id, result.iterations, len(result.tool_calls),
        )

        return {
            "status": "completed",
            "output": output_text,
            "iterations": result.iterations,
            "tool_calls_count": len(result.tool_calls),
            "message_id": assistant_message_id,
        }

    except Exception as e:
        logger.error(
            "conversation_agent_task failed: conversation=%s error=%s",
            conversation_id, str(e),
        )
        emit_event("error", {"error": str(e)})
        return {"status": "error", "error": str(e)}
