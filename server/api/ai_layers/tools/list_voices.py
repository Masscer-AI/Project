from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from api.voices.access import (
    resolve_accessible_voices,
    resolve_voice_for_speech,
    voice_is_accessible,
)
from api.voices.models import VoiceProvider


class ListVoicesParams(BaseModel):
    target: Literal["speech", "dialogue"] = Field(
        description=(
            "Use 'speech' before create_speech. Use 'dialogue' before "
            "generate_dialogue, which creates one multi-speaker audio."
        )
    )


class VoiceListItem(BaseModel):
    voice_id: str = Field(description="UUID to pass to the requested generation tool.")
    name: str
    provider: str
    scope: str
    is_default: bool


class ListVoicesResult(BaseModel):
    voices: list[VoiceListItem]
    default_voice_id: str | None = Field(
        description=(
            "Effective compatible default voice UUID, or null when no compatible "
            "agent default exists for the requested target."
        )
    )


def _list_voices_impl(
    *,
    target: Literal["speech", "dialogue"],
    conversation_id: str,
    user_id: int | None,
    agent_slug: str | None,
) -> ListVoicesResult:
    from django.contrib.auth.models import User

    from api.ai_layers.models import Agent
    from api.messaging.models import Conversation

    try:
        conversation = Conversation.objects.select_related(
            "organization",
            "user",
            "chat_widget",
        ).get(id=conversation_id)
    except Conversation.DoesNotExist as exc:
        raise ValueError("Conversation not found") from exc

    user = None
    if user_id is not None:
        user = User.objects.filter(id=user_id).first()
    if user is None:
        user = getattr(conversation, "user", None)

    agent = None
    if agent_slug:
        agent = (
            Agent.objects.select_related("default_voice", "organization")
            .filter(slug=agent_slug)
            .first()
        )

    organization = getattr(conversation, "organization", None)
    if organization is None and agent is not None:
        organization = getattr(agent, "organization", None)
    if organization is None and user is not None:
        from api.messaging.tasks import get_user_organization

        organization = get_user_organization(user)
    if organization is None:
        widget = getattr(conversation, "chat_widget", None)
        widget_agent = getattr(widget, "agent", None) if widget is not None else None
        organization = (
            getattr(widget_agent, "organization", None)
            if widget_agent is not None
            else None
        )

    voices = list(
        resolve_accessible_voices(user=user, organization=organization)
    )
    if target == "dialogue":
        voices = [voice for voice in voices if voice.provider == VoiceProvider.ELEVENLABS]
        agent_default = getattr(agent, "default_voice", None) if agent else None
        default_voice_id = (
            str(agent_default.id)
            if agent_default is not None
            and agent_default.provider == VoiceProvider.ELEVENLABS
            and voice_is_accessible(agent_default, user=user, organization=organization)
            else None
        )
    else:
        default_voice = resolve_voice_for_speech(
            voice_id=None,
            agent=agent,
            user=user,
            organization=organization,
        )
        default_voice_id = str(default_voice.id)

    items = [
        VoiceListItem(
            voice_id=str(voice.id),
            name=voice.name,
            provider=voice.provider,
            scope=voice.scope,
            is_default=str(voice.id) == default_voice_id,
        )
        for voice in voices
    ]
    return ListVoicesResult(
        voices=items,
        default_voice_id=default_voice_id,
    )


def get_tool(
    conversation_id: str | None = None,
    user_id: int | None = None,
    agent_slug: str | None = None,
    **kwargs,
) -> dict:
    if not conversation_id:
        raise ValueError("list_voices requires conversation_id in tool context")

    def list_voices(target: Literal["speech", "dialogue"]) -> ListVoicesResult:
        return _list_voices_impl(
            target=target,
            conversation_id=conversation_id,
            user_id=user_id,
            agent_slug=agent_slug,
        )

    return {
        "name": "list_voices",
        "description": (
            "List voices accessible in the current conversation and their UUIDs. "
            "Use target='speech' before create_speech; it returns OpenAI and ElevenLabs "
            "voices. Use target='dialogue' before generate_dialogue; it returns only "
            "ElevenLabs voices suitable for multi-speaker dialogue."
        ),
        "parameters": ListVoicesParams,
        "function": list_voices,
    }
