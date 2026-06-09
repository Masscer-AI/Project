"""
Celery task for platform assistant (onboarding / org help) conversations.

Separate from conversation_agent_task — fixed tools, single agent, code-managed prompt.
"""

from __future__ import annotations

import logging
import time
import traceback as tb

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def platform_assistant_task(
    conversation_id: str,
    user_inputs: list[dict],
    agent_slug: str,
    user_id: int,
    regenerate_message_id: int | None = None,
    client_datetime: dict | None = None,
    max_iterations: int = 10,
):
    from api.ai_layers.agent_loop import AgentLoop, CancelledError
    from api.ai_layers.models import Agent, AgentKind, AgentSession
    from api.ai_layers.platform_assistant import build_platform_assistant_instructions
    from api.ai_layers.platform_tools import list_platform_tools, resolve_platform_tools
    from api.ai_layers.schemas import (
        AgentRef,
        AgentSessionInputs,
        AgentSessionOutputs,
        ModelRef,
        OutputError,
        OutputValue,
    )
    from api.ai_layers.tasks import (
        _agent_clock_context,
        _agent_loop_provider_from_llm,
        _build_agent_loop_inputs,
        _build_user_message_text,
        _resolve_user_inputs_and_attachments,
        _serialize_prev_messages,
    )
    from api.messaging.models import Conversation, Message
    from api.messaging.takeover import is_takeover_active
    from api.notify.actions import notify_user

    notification_route_id = user_id

    def emit_event(event_type: str, data: dict) -> None:
        payload = {"type": event_type, "conversation_id": conversation_id, **data}
        notify_user(notification_route_id, "agent_events_channel", payload)

    def emit_finished(data: dict) -> None:
        payload = {"conversation_id": conversation_id, **data}
        notify_user(notification_route_id, "agent_loop_finished", payload)

    try:
        conversation = Conversation.objects.select_related("organization", "user").get(
            id=conversation_id
        )
    except Conversation.DoesNotExist:
        emit_event("error", {"error": f"Conversation {conversation_id} not found"})
        return {"status": "error", "error": "Conversation not found"}

    if is_takeover_active(conversation):
        return {"status": "skipped", "reason": "takeover_active"}

    try:
        agent = Agent.objects.select_related("llm", "llm__provider", "organization").get(
            slug=agent_slug,
            agent_kind=AgentKind.PLATFORM_ASSISTANT,
        )
    except Agent.DoesNotExist:
        emit_event("error", {"error": f"Platform assistant '{agent_slug}' not found"})
        return {"status": "error", "error": "Platform assistant not found"}

    organization = agent.organization or conversation.organization
    if not organization:
        emit_event("error", {"error": "No organization context for platform assistant"})
        return {"status": "error", "error": "No organization context"}

    from api.consumption.actions import _check_org_subscription, notify_org_billing_denied

    billing_org_id = organization.id
    allowed, billing_reason = _check_org_subscription(billing_org_id)
    if not allowed:
        notify_org_billing_denied(user_id, billing_reason)
        emit_finished(
            {
                "output": "",
                "message_id": None,
                "versions": [],
                "attachments": [],
                "iterations": 0,
                "tool_calls_count": 0,
                "status": "error",
                "error": "organization_billing_blocked",
                "billing_reason": billing_reason,
            }
        )
        return {"status": "error", "error": "organization_billing_blocked"}

    try:
        resolved_inputs, message_attachments, attachment_objects = (
            _resolve_user_inputs_and_attachments(
                user_inputs, conversation_id=conversation_id
            )
        )
    except ValueError as e:
        emit_event("error", {"error": str(e)})
        return {"status": "error", "error": str(e)}

    user_message_text = _build_user_message_text(resolved_inputs)
    agent_event_log: list[dict] = []

    try:
        if regenerate_message_id:
            try:
                user_message = Message.objects.get(
                    id=regenerate_message_id,
                    conversation=conversation,
                    type="user",
                )
                user_message.text = user_message_text
                user_message.attachments = message_attachments
                user_message.save(update_fields=["text", "attachments"])
                Message.objects.filter(
                    conversation=conversation,
                    id__gt=user_message.id,
                ).delete()
            except Message.DoesNotExist:
                emit_event("error", {"error": "Message to regenerate not found"})
                return {"status": "error", "error": "Message to regenerate not found"}
        else:
            user_message = Message.objects.create(
                conversation=conversation,
                type="user",
                text=user_message_text,
                attachments=message_attachments,
            )
            for att in attachment_objects:
                att.message = user_message
                att.save(update_fields=["message"])

        prev_messages = _serialize_prev_messages(conversation, user_message.id)
        clock_context = _agent_clock_context(client_datetime)
        instructions = build_platform_assistant_instructions(
            organization, clock_context=clock_context
        )

        llm = agent.llm
        model_slug = llm.slug if llm else (agent.model_slug or "gpt-5.2")
        platform_tool_names = list_platform_tools()

        model_ref = ModelRef(
            id=llm.id if llm else 0,
            slug=model_slug,
            provider=llm.provider.name if llm else "openai",
        )
        inputs_data = AgentSessionInputs(
            instructions=instructions,
            user_inputs=resolved_inputs,
            user_message_text=user_message_text,
            tool_names=platform_tool_names,
            plugin_slugs=[],
            agent=AgentRef(id=agent.id, slug=agent.slug, name=agent.name),
            model=model_ref,
            multiagentic_modality="isolated",
            prev_messages=prev_messages,
            max_iterations=max_iterations,
        ).model_dump()

        session = AgentSession.objects.create(
            conversation=conversation,
            user_message=user_message,
            task_type="platform_assistant",
            inputs=inputs_data,
            outputs={},
            agent_index=0,
        )
        start_time = time.perf_counter()

        def on_event(event_type: str, data: dict) -> None:
            from django.utils import timezone as _tz

            agent_event_log.append(
                {
                    "type": event_type,
                    "tool_name": data.get("tool_name"),
                    "iteration": data.get("iteration"),
                    "duration": data.get("duration"),
                    "error": data.get("error"),
                    "ts": _tz.now().isoformat(),
                }
            )
            emit_event(
                event_type,
                {
                    "agent_slug": agent.slug,
                    "agent_name": agent.name,
                    **data,
                },
            )

        def is_cancelled() -> bool:
            from django.core.cache import cache

            if cache.get(f"cancel_task_{conversation_id}"):
                return True
            if is_takeover_active(conversation):
                return True
            return AgentSession.objects.filter(
                id=session.id, dismissed_at__isnull=False
            ).exists()

        tools = resolve_platform_tools(
            platform_tool_names,
            conversation_id=conversation_id,
            user_id=user_id,
            agent_slug=agent.slug,
            organization_id=organization.id,
        )

        loop = AgentLoop.create(
            provider=_agent_loop_provider_from_llm(llm),
            tools=tools,
            instructions=instructions,
            model=model_slug,
            max_iterations=max_iterations,
            on_event=on_event,
            check_cancelled=is_cancelled,
        )

        openai_inputs = _build_agent_loop_inputs(
            prev_messages=prev_messages,
            current_user_text=user_message_text,
            current_user_attachments=message_attachments,
            agent_slug=agent.slug,
            multiagentic_modality="isolated",
        )

        try:
            result = loop.run(openai_inputs)
        except CancelledError:
            from django.utils import timezone

            session.ended_at = timezone.now()
            session.event_log = agent_event_log
            session.save(update_fields=["ended_at", "event_log"])
            emit_finished(
                {
                    "output": "Generation stopped by user.",
                    "message_id": None,
                    "versions": [],
                    "attachments": [],
                    "iterations": 0,
                    "tool_calls_count": 0,
                    "status": "cancelled",
                }
            )
            return {"status": "cancelled"}

        if isinstance(result.output, str):
            output_value = OutputValue(type="string", value=result.output)
            output_text = result.output
        elif hasattr(result.output, "model_dump"):
            import json as _json

            dump = result.output.model_dump(mode="json")
            output_value = OutputValue(type="json", value=dump)
            output_text = _json.dumps(dump, default=str)
        else:
            output_text = str(result.output)
            output_value = OutputValue(type="string", value=output_text)

        outputs_data = AgentSessionOutputs(
            messages=result.messages,
            output=output_value,
            usage=result.usage,
            status="completed",
            error=None,
        ).model_dump()

        from django.utils import timezone

        session.outputs = outputs_data
        session.event_log = agent_event_log
        session.iterations = result.iterations
        session.tool_calls_count = len(result.tool_calls or [])
        session.ended_at = timezone.now()
        session.total_duration = time.perf_counter() - start_time
        session.save()

        version = {
            "agent_slug": agent.slug,
            "agent_name": agent.name,
            "type": "assistant",
            "text": output_text,
            "sources": [],
            "usage": {
                "prompt_tokens": result.usage.get("prompt_tokens", 0),
                "completion_tokens": result.usage.get("completion_tokens", 0),
                "total_tokens": result.usage.get("total_tokens", 0),
                "model_slug": model_slug,
            },
        }
        emit_event("agent_version_ready", {"version": version})

        assistant_msg = Message.objects.create(
            conversation=conversation,
            type="assistant",
            text=output_text,
            versions=[version],
            attachments=[],
        )
        session.assistant_message = assistant_msg
        session.save(update_fields=["assistant_message"])

        emit_finished(
            {
                "output": output_text,
                "message_id": assistant_msg.id,
                "versions": [version],
                "attachments": [],
                "iterations": result.iterations,
                "tool_calls_count": len(result.tool_calls or []),
            }
        )

        return {
            "status": "completed",
            "output": output_text,
            "message_id": assistant_msg.id,
            "iterations": result.iterations,
            "tool_calls_count": len(result.tool_calls or []),
        }

    except Exception as e:
        logger.error(
            "platform_assistant_task failed: conversation=%s error=%s",
            conversation_id,
            str(e),
        )
        emit_event("error", {"error": str(e)})
        emit_finished(
            {
                "output": "",
                "message_id": None,
                "versions": [],
                "attachments": [],
                "iterations": 0,
                "tool_calls_count": 0,
                "status": "error",
                "error": str(e),
            }
        )
        return {"status": "error", "error": str(e)}
