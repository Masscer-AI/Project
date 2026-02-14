import logging
import time
import traceback as tb
from celery import shared_task
from .actions import generate_agent_profile_picture

logger = logging.getLogger(__name__)


def _serialize_prev_messages(conversation, before_message_id, limit=50):
    """Load and serialize prev messages for reproducibility."""
    from api.messaging.models import Message

    qs = Message.objects.filter(
        conversation=conversation,
        id__lt=before_message_id,
    ).order_by("-id")[:limit]
    return [
        {"type": m.type, "text": m.text, "versions": m.versions}
        for m in reversed(list(qs))
    ]


@shared_task
def async_generate_agent_profile_picture(agent_id: int):
    result = generate_agent_profile_picture(agent_id)
    return result


def _build_user_message_text(user_inputs: list[dict]) -> str:
    """
    Build a plain-text user message from user_inputs.
    """
    parts = []
    for inp in user_inputs:
        input_type = inp.get("type", "")
        if input_type == "input_text":
            text = inp.get("text", "").strip()
            if text:
                parts.append(text)
        elif input_type == "input_image":
            parts.append("[Image attached]")
    return "\n".join(parts) if parts else ""


def _resolve_user_inputs_and_attachments(user_inputs: list[dict]):
    """
    Resolve input_image with id to base64 content; build attachments for Message.
    Returns (resolved_user_inputs, message_attachments_json, attachment_objects).
    attachment_objects are the MessageAttachment instances to link to the message later.
    """
    import base64
    from api.messaging.models import MessageAttachment
    from django.conf import settings

    resolved = []
    message_attachments = []
    attachment_objects = []

    for inp in user_inputs:
        input_type = inp.get("type", "")
        if input_type == "input_image" and inp.get("id"):
            try:
                att = MessageAttachment.objects.get(id=inp["id"])
            except MessageAttachment.DoesNotExist:
                logger.warning("MessageAttachment %s not found, skipping", inp["id"])
                continue
            attachment_objects.append(att)
            with att.file.open("rb") as f:
                raw = f.read()
            b64 = base64.b64encode(raw).decode("ascii")
            content_type = att.content_type or "image/png"
            data_url = f"data:{content_type};base64,{b64}"

            resolved.append({"type": "input_image", "content": data_url})
            api_base = getattr(settings, "API_BASE_URL", None) or ""
            url = att.file.url
            if api_base and not url.startswith("http"):
                display_url = f"{api_base.rstrip('/')}{url}"
            else:
                display_url = url
            message_attachments.append({
                "type": "image",
                "content": display_url,
                "name": att.file.name.split("/")[-1] or "image.png",
            })
        else:
            resolved.append(dict(inp))

    return resolved, message_attachments, attachment_objects


@shared_task
def conversation_agent_task(
    conversation_id: str,
    user_inputs: list[dict],
    tool_names: list[str],
    agent_slugs: list[str],
    multiagentic_modality: str = "isolated",
    max_iterations: int = 10,
    user_id: int | None = None,
):
    """
    Celery task that runs an AgentLoop for one or more agents in a conversation.

    Resolves agents from their slugs, derives instructions and model for each,
    executes the agent loop for each (sequentially), and emits real-time status
    updates via Redis pub/sub (notify_user) so the frontend can show progress.

    For multiagentic_modality="grupal", each agent sees previous agents' outputs
    as context. For "isolated", each agent only sees the user message.

    Args:
        conversation_id: UUID of the conversation
        user_inputs: list of input dicts, e.g. [{"type": "input_text", "text": "..."}]
        tool_names: list of tool names to resolve from the registry
        agent_slugs: list of Agent slugs to run (in order)
        multiagentic_modality: "isolated" or "grupal"
        user_id: ID of the user (for notifications)

    Returns:
        dict with status, output, iterations, tool_calls_count, message_id
    """
    from api.ai_layers.agent_loop import AgentLoop
    from api.ai_layers.models import Agent, AgentSession
    from api.ai_layers.tools import resolve_tools
    from api.ai_layers.schemas import (
        AgentSessionInputs,
        AgentSessionOutputs,
        AgentRef,
        ModelRef,
        OutputValue,
        OutputError,
    )
    from api.notify.actions import notify_user
    from api.messaging.models import Conversation, Message

    # Resolve input_image ids to content; get attachments for Message
    resolved_inputs, message_attachments, attachment_objects = _resolve_user_inputs_and_attachments(
        user_inputs
    )
    user_message_text = _build_user_message_text(resolved_inputs)

    def emit_event(event_type: str, data: dict) -> None:
        payload = {"type": event_type, "conversation_id": conversation_id, **data}
        notify_user(user_id, "agent_events_channel", payload)

    def emit_finished(data: dict) -> None:
        payload = {"conversation_id": conversation_id, **data}
        notify_user(user_id, "agent_loop_finished", payload)

    logger.info(
        "conversation_agent_task started: conversation=%s user=%s agents=%s tools=%s modality=%s",
        conversation_id, user_id, agent_slugs, tool_names, multiagentic_modality,
    )

    agent_sessions_created = []
    try:
        tools = resolve_tools(tool_names) if tool_names else []

        # ---- Save user message ----
        try:
            conversation = Conversation.objects.get(id=conversation_id)
            user_message = Message.objects.create(
                conversation=conversation,
                type="user",
                text=user_message_text,
                attachments=message_attachments,
            )
            for att in attachment_objects:
                att.message = user_message
                att.save(update_fields=["message"])
        except Conversation.DoesNotExist:
            logger.error("Conversation %s not found", conversation_id)
            emit_event("error", {"error": f"Conversation {conversation_id} not found"})
            return {"status": "error", "error": "Conversation not found"}

        # ---- Resolve agents in order ----
        agents_by_slug = {a.slug: a for a in Agent.objects.filter(slug__in=agent_slugs)}
        agents_ordered = [agents_by_slug[s] for s in agent_slugs if s in agents_by_slug]
        if not agents_ordered:
            emit_event("error", {"error": "No valid agents found"})
            return {"status": "error", "error": "No valid agents found"}

        versions = []
        total_iterations = 0
        total_tool_calls = 0

        prev_messages = _serialize_prev_messages(conversation, user_message.id)

        for index, agent in enumerate(agents_ordered):
            instructions = agent.format_prompt()
            llm = agent.llm
            model_slug = llm.slug if llm else (agent.model_slug or "gpt-5.2")

            # For grupal: prepend previous agents' outputs to instructions
            if multiagentic_modality == "grupal" and versions:
                prev_context = (
                    "\n\nYou must consider that the other AI(s) in the conversation "
                    "are other users and refer to them as such. ONLY GIVE YOUR RESPONSE."
                    "\n\nResponses from other AIs so far:\n"
                )
                for v in versions:
                    prev_context += f"\n--- {v.get('agent_name', 'Unknown')} ---\n{v.get('text', '')}\n"
                instructions = instructions + prev_context

            # ---- Create AgentSession (inputs) ----
            model_ref = ModelRef(
                id=llm.id if llm else 0,
                slug=model_slug,
                provider=llm.provider.name if llm else "openai",
            )
            inputs_data = AgentSessionInputs(
                instructions=instructions,
                user_inputs=resolved_inputs,
                user_message_text=user_message_text,
                tool_names=tool_names,
                agent=AgentRef(id=agent.id, slug=agent.slug, name=agent.name),
                model=model_ref,
                multiagentic_modality=multiagentic_modality,
                prev_messages=prev_messages,
                max_iterations=max_iterations,
            ).model_dump()

            session = AgentSession.objects.create(
                conversation=conversation,
                user_message=user_message,
                task_type="chat_message",
                inputs=inputs_data,
                outputs={},
                agent_index=index,
            )
            agent_sessions_created.append(session)
            start_time = time.perf_counter()

            def on_event(event_type: str, data: dict) -> None:
                payload = {
                    "type": event_type,
                    "conversation_id": conversation_id,
                    "agent_slug": agent.slug,
                    "agent_name": agent.name,
                    **data,
                }
                notify_user(user_id, "agent_events_channel", payload)

            loop = AgentLoop(
                tools=tools,
                instructions=instructions,
                model=model_slug,
                max_iterations=max_iterations,
                on_event=on_event,
            )
            result = loop.run(user_message_text, user_inputs=resolved_inputs)

            # ---- Update AgentSession (outputs) ----
            from django.utils import timezone

            if isinstance(result.output, str):
                output_value = OutputValue(type="string", value=result.output)
            elif hasattr(result.output, "model_dump"):
                dump = result.output.model_dump(mode="json")
                output_value = OutputValue(type="json", value=dump)
            else:
                output_value = OutputValue(type="string", value=str(result.output))

            outputs_data = AgentSessionOutputs(
                messages=result.messages,
                output=output_value,
                usage=result.usage,
                status="completed",
                error=None,
            ).model_dump()

            session.outputs = outputs_data
            session.iterations = result.iterations
            session.tool_calls_count = len(result.tool_calls)
            session.ended_at = timezone.now()
            session.total_duration = time.perf_counter() - start_time
            session.save()

            # ---- Extract output text for version ----
            import json as _json
            if isinstance(result.output, str):
                output_text = result.output
            elif hasattr(result.output, "model_dump"):
                output_text = _json.dumps(result.output.model_dump(), default=str)
            else:
                output_text = str(result.output)

            version = {
                "agent_slug": agent.slug,
                "agent_name": agent.name,
                "type": "assistant",
                "usage": {
                    "prompt_tokens": result.usage.get("prompt_tokens", 0),
                    "completion_tokens": result.usage.get("completion_tokens", 0),
                    "total_tokens": result.usage.get("total_tokens", 0),
                    "model_slug": model_slug,
                },
            }
            version["text"] = output_text
            versions.append(version)

            total_iterations += result.iterations
            total_tool_calls += len(result.tool_calls)

            # Emit version immediately so frontend can display it in real time
            emit_event("agent_version_ready", {"version": version})

            emit_event("agent_complete", {
                "agent_slug": agent.slug,
                "agent_name": agent.name,
                "index": index + 1,
                "total": len(agents_ordered),
            })

        # ---- Save assistant message with all versions ----
        assistant_message_id = None
        primary_text = versions[0]["text"] if versions else ""
        try:
            conversation = Conversation.objects.get(id=conversation_id)
            assistant_msg = Message.objects.create(
                conversation=conversation,
                type="assistant",
                text=primary_text,
                versions=versions,
            )
            assistant_message_id = assistant_msg.id
            for s in agent_sessions_created:
                s.assistant_message = assistant_msg
                s.save(update_fields=["assistant_message"])
            conversation.generate_title()
        except Conversation.DoesNotExist:
            logger.warning(
                "Conversation %s not found when saving assistant message",
                conversation_id,
            )

        emit_finished({
            "output": primary_text,
            "message_id": assistant_message_id,
            "versions": versions,
            "iterations": total_iterations,
            "tool_calls_count": total_tool_calls,
        })

        logger.info(
            "conversation_agent_task completed: conversation=%s agents=%d iterations=%d tool_calls=%d",
            conversation_id, len(versions), total_iterations, total_tool_calls,
        )

        return {
            "status": "completed",
            "output": primary_text,
            "iterations": total_iterations,
            "tool_calls_count": total_tool_calls,
            "message_id": assistant_message_id,
        }

    except Exception as e:
        logger.error(
            "conversation_agent_task failed: conversation=%s error=%s",
            conversation_id, str(e),
        )
        emit_event("error", {"error": str(e)})

        # Update last created session with error outputs if any
        if agent_sessions_created:
            from django.utils import timezone

            last_session = agent_sessions_created[-1]
            outputs_data = AgentSessionOutputs(
                messages=last_session.outputs.get("messages", []),
                output=OutputValue(type="string", value=""),
                usage=last_session.outputs.get("usage", {}),
                status="error",
                error=OutputError(message=str(e), traceback=tb.format_exc()),
            ).model_dump()
            last_session.outputs = outputs_data
            last_session.ended_at = timezone.now()
            last_session.tool_calls_count = sum(
                1 for m in last_session.outputs.get("messages", [])
                if m.get("type") == "function_call"
            )
            if last_session.started_at:
                last_session.total_duration = (
                    timezone.now() - last_session.started_at
                ).total_seconds()
            last_session.save(
                update_fields=["outputs", "ended_at", "total_duration", "tool_calls_count"]
            )

        return {"status": "error", "error": str(e)}
