"""
Tool: create_speech

Generates speech audio from text using OpenAI gpt-4o-mini-tts and stores it
as a MessageAttachment(kind="file"), so it can be rendered in the frontend
and later referenced by attachment_id.

The model supports an `instructions` parameter that controls accent, tone,
speed, emotional range, whispering, impressions, etc.

Availability:
- Must be explicitly enabled via AgentTask tool_names (tool registry allowlist)
- Must pass org/user feature flag: "chat-generate-speech"
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Literal

import requests
from django.core.files.base import ContentFile
from django.utils.text import slugify
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

OutputFormat = Literal["mp3", "wav"]

# Full voice list for gpt-4o-mini-tts (per OpenAI docs 2026).
# For best quality OpenAI recommends "marin" or "cedar".
OPENAI_VOICES: set[str] = {
    "alloy",
    "ash",
    "ballad",
    "coral",
    "echo",
    "fable",
    "nova",
    "onyx",
    "sage",
    "shimmer",
    "verse",
    "marin",
    "cedar",
}


class CreateSpeechParams(BaseModel):
    text: str = Field(description="Text to convert into speech audio.")
    voice: str = Field(
        default="coral",
        description=(
            "Voice id. Options: alloy, ash, ballad, coral, echo, fable, "
            "nova, onyx, sage, shimmer, verse, marin, cedar. "
            "For best quality use marin or cedar."
        ),
    )
    instructions: str = Field(
        default="",
        description=(
            "Optional speech style instructions for gpt-4o-mini-tts. "
            "Controls accent, tone, speed, emotional range, whispering, etc. "
            "Example: 'Speak in a warm, cheerful tone with a slight British accent.'"
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
    voice: str = Field(description="Voice used.")
    output_format: OutputFormat = Field(description="Output format used.")


def _mime_for_format(fmt: OutputFormat) -> str:
    return "audio/mpeg" if fmt == "mp3" else "audio/wav"


def _generate_openai_tts_bytes(
    *,
    text: str,
    voice: str,
    instructions: str,
    output_format: OutputFormat,
) -> bytes:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured")

    payload: dict = {
        "model": "gpt-4o-mini-tts",
        "input": text,
        "voice": voice,
        "response_format": output_format,
    }
    if instructions:
        payload["instructions"] = instructions

    resp = requests.post(
        "https://api.openai.com/v1/audio/speech",
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    return resp.content


def _create_speech_impl(
    *,
    text: str,
    voice: str,
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

    voice = (voice or "").strip() or "coral"
    if voice not in OPENAI_VOICES:
        raise ValueError(f"Unsupported voice '{voice}'. Allowed: {', '.join(sorted(OPENAI_VOICES))}")

    instructions = (instructions or "").strip()

    # ---- Load conversation + resolve user ----
    try:
        conversation = Conversation.objects.select_related("organization").get(id=conversation_id)
    except Conversation.DoesNotExist:
        raise ValueError("Conversation not found")

    user = None
    if user_id is not None:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            user = None

    # ---- Feature gating ----
    enabled, _reason = FeatureFlagService.is_feature_enabled(
        "chat-generate-speech",
        organization=getattr(conversation, "organization", None),
        user=user,
    )
    if not enabled:
        raise ValueError("The 'chat-generate-speech' feature is not enabled.")

    # ---- Generate bytes ----
    try:
        audio_bytes = _generate_openai_tts_bytes(
            text=text,
            voice=voice,
            instructions=instructions,
            output_format=output_format,
        )
    except Exception as e:
        logger.exception("Failed to generate speech via OpenAI")
        raise ValueError(f"Failed to generate speech: {str(e)}")

    # ---- Resolve agent (optional) ----
    agent_obj = None
    if agent_slug:
        try:
            from api.ai_layers.models import Agent

            agent_obj = Agent.objects.get(slug=agent_slug)
        except Exception:
            agent_obj = None

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
            "voice": voice,
            "instructions": instructions[:2000],
            "output_format": output_format,
            "model": "gpt-4o-mini-tts",
            "provider": "openai",
        },
    )

    content_url = attachment.file.url if attachment.file else ""

    return CreateSpeechResult(
        attachment_id=str(attachment.id),
        name=safe_name,
        content=content_url,
        content_type=content_type,
        voice=voice,
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
        voice: str = "coral",
        instructions: str = "",
        output_format: OutputFormat = "mp3",
    ) -> CreateSpeechResult:
        return _create_speech_impl(
            text=text,
            voice=voice,
            instructions=instructions,
            output_format=output_format,
            conversation_id=conversation_id,
            user_id=user_id,
            agent_slug=agent_slug,
        )

    return {
        "name": "create_speech",
        "description": (
            "Generate speech audio from text using OpenAI gpt-4o-mini-tts. "
            "Use this when the user asks for an audio/speech version of content. "
            "You can control accent, tone, speed, emotional range, whispering, "
            "and other speech characteristics via the 'instructions' parameter. "
            "Available voices: alloy, ash, ballad, coral, echo, fable, nova, "
            "onyx, sage, shimmer, verse, marin, cedar. "
            "For best quality use marin or cedar. "
            "Returns an attachment_id and a file URL that will appear in the chat."
        ),
        "parameters": CreateSpeechParams,
        "function": create_speech,
    }
