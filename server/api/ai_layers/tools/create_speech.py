"""
Tool: create_speech

Generates speech audio from text using voices from the catalog (OpenAI or
ElevenLabs) and stores it as a MessageAttachment(kind="file").

Availability:
- Must be explicitly enabled via AgentTask tool_names (tool registry allowlist)
- App chat: org/user feature flag "chat-generate-speech"
- Widget / WhatsApp: gated only by widget or WSNumber capabilities (no app FF)
"""

from __future__ import annotations

import logging
import uuid
from typing import Literal

from django.core.files.base import ContentFile
from django.utils.text import slugify
from pydantic import BaseModel, Field

from api.voices.access import resolve_voice_for_speech
from api.voices.synthesis import OutputFormat, synthesize_speech_bytes

logger = logging.getLogger(__name__)


class CreateSpeechParams(BaseModel):
    text: str = Field(description="Text to convert into speech audio.")
    voice_id: str | None = Field(
        default=None,
        description="UUID of a voice from the accessible voices catalog.",
    )
    instructions: str = Field(
        default="",
        description=(
            "Optional speech style instructions (OpenAI voices only). "
            "Controls accent, tone, speed, emotional range, whispering, etc."
        ),
    )
    output_format: OutputFormat = Field(
        default="mp3",
        description="Audio format: mp3 or wav.",
    )


class CreateSpeechResult(BaseModel):
    attachment_id: str = Field(description="UUID of the created MessageAttachment.")
    name: str = Field(description="Display name (slugified).")
    content: str = Field(description="Attachment file URL (relative /media/... path).")
    content_type: str = Field(description="MIME type, e.g. audio/mpeg.")
    voice_id: str = Field(description="Catalog voice UUID used.")
    voice_name: str = Field(description="Display name of the voice used.")
    output_format: OutputFormat = Field(description="Output format used.")


def _mime_for_format(fmt: OutputFormat) -> str:
    return "audio/mpeg" if fmt == "mp3" else "audio/wav"


def _resolve_organization(conversation):
    organization = getattr(conversation, "organization", None)
    if organization is not None:
        return organization
    user = getattr(conversation, "user", None)
    if user is not None:
        from api.messaging.tasks import get_user_organization

        return get_user_organization(user)
    widget = getattr(conversation, "chat_widget", None)
    if widget is not None:
        widget_agent = getattr(widget, "agent", None)
        if widget_agent is not None:
            return getattr(widget_agent, "organization", None)
    return None


def _create_speech_impl(
    *,
    text: str,
    voice_id: str | None,
    instructions: str,
    output_format: OutputFormat,
    conversation_id: str,
    user_id: int | None,
    agent_slug: str | None,
) -> CreateSpeechResult:
    from django.contrib.auth.models import User

    from api.authenticate.services import FeatureFlagService
    from api.messaging.models import Conversation, MessageAttachment

    text = (text or "").strip()
    if not text:
        raise ValueError("text is required")

    instructions = (instructions or "").strip()

    try:
        conversation = Conversation.objects.select_related("organization", "chat_widget").get(
            id=conversation_id
        )
    except Conversation.DoesNotExist:
        raise ValueError("Conversation not found")

    user = None
    if user_id is not None:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            user = None

    from api.ai_layers.tools.embedded_channels import conversation_uses_capability_gated_media_tools

    if not conversation_uses_capability_gated_media_tools(conversation):
        enabled, _reason = FeatureFlagService.is_feature_enabled(
            "chat-generate-speech",
            organization=getattr(conversation, "organization", None),
            user=user,
        )
        if not enabled:
            raise ValueError("The 'chat-generate-speech' feature is not enabled.")

    agent_obj = None
    if agent_slug:
        try:
            from api.ai_layers.models import Agent

            agent_obj = Agent.objects.select_related("default_voice").get(slug=agent_slug)
        except Exception:
            agent_obj = None

    organization = _resolve_organization(conversation)
    if organization is None and agent_obj is not None:
        organization = getattr(agent_obj, "organization", None)

    voice = resolve_voice_for_speech(
        voice_id=voice_id,
        agent=agent_obj,
        user=user or getattr(conversation, "user", None),
        organization=organization,
    )

    try:
        audio_bytes, model_used = synthesize_speech_bytes(
            voice=voice,
            text=text,
            instructions=instructions,
            output_format=output_format,
        )
    except Exception as e:
        logger.exception("Failed to generate speech for voice=%s", voice.id)
        raise ValueError(f"Failed to generate speech: {str(e)}") from e

    safe_name = slugify(text[:60]) or "speech"
    filename = f"{safe_name}-{uuid.uuid4().hex[:8]}.{output_format}"
    content_type = _mime_for_format(output_format)
    file_obj = ContentFile(audio_bytes, name=filename)

    attachment = MessageAttachment.objects.create(
        conversation=conversation,
        user=user,
        agent=agent_obj,
        kind="file",
        file=file_obj,
        content_type=content_type,
        metadata={
            "text": text[:5000],
            "voice_id": str(voice.id),
            "voice_name": voice.name,
            "provider_voice_id": voice.provider_voice_id,
            "instructions": instructions[:2000],
            "output_format": output_format,
            "model": model_used,
            "provider": voice.provider,
        },
    )

    content_url = attachment.file.url if attachment.file else ""

    return CreateSpeechResult(
        attachment_id=str(attachment.id),
        name=safe_name,
        content=content_url,
        content_type=content_type,
        voice_id=str(voice.id),
        voice_name=voice.name,
        output_format=output_format,
    )


def get_tool(
    conversation_id: str | None = None,
    user_id: int | None = None,
    agent_slug: str | None = None,
    **kwargs,
) -> dict:
    if not conversation_id:
        raise ValueError("create_speech requires conversation_id in tool context")

    def create_speech(
        text: str,
        voice_id: str | None = None,
        instructions: str = "",
        output_format: OutputFormat = "mp3",
    ) -> CreateSpeechResult:
        return _create_speech_impl(
            text=text,
            voice_id=voice_id,
            instructions=instructions,
            output_format=output_format,
            conversation_id=conversation_id,
            user_id=user_id,
            agent_slug=agent_slug,
        )

    return {
        "name": "create_speech",
        "description": (
            "Generate speech audio from text using a voice from the catalog. "
            "Use this when the user asks for an audio/speech version of content. "
            "Pass voice_id (UUID) from the available voices list in your instructions. "
            "For OpenAI voices you can control accent, tone, speed, and style via "
            "the instructions parameter. "
            "Returns an attachment_id and a file URL that will appear in the chat."
        ),
        "parameters": CreateSpeechParams,
        "function": create_speech,
    }
