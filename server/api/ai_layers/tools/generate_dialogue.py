"""
Tool: generate_dialogue

Generates a single multi-speaker audio attachment with ElevenLabs Text to
Dialogue (Eleven v3). Each turn must resolve to an accessible ElevenLabs voice.
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from django.core.files.base import ContentFile
from django.utils.text import slugify
from pydantic import BaseModel, Field

from api.voices.access import resolve_voice_for_speech
from api.voices.models import VoiceProvider
from api.voices.synthesis import generate_elevenlabs_dialogue_bytes

logger = logging.getLogger(__name__)

MAX_DIALOGUE_CHARACTERS = 2_000


class DialogueTurn(BaseModel):
    text: Annotated[str, Field(description="The speaker's dialogue text.")]
    voice_id: str | None = Field(
        default=None,
        description=(
            "UUID returned by list_voices with target='dialogue'. Omit only to use "
            "the agent's default voice when it is an accessible ElevenLabs voice."
        ),
    )
    instructions: str = Field(
        default="",
        description=(
            "Optional Eleven v3 audio tag direction, such as 'whispering', "
            "'giggling', or 'gentle footsteps'. It is inserted before this turn."
        ),
    )


class GenerateDialogueParams(BaseModel):
    turns: Annotated[
        list[DialogueTurn],
        Field(
            min_length=2,
            max_length=50,
            description=(
                "Ordered dialogue turns. Keep the combined text, including audio "
                "tags, at or below 2,000 characters."
            ),
        ),
    ]
    seed: int | None = Field(
        default=None,
        description="Optional ElevenLabs seed for more consistent regenerations.",
    )


class DialogueVoice(BaseModel):
    voice_id: str
    voice_name: str


class GenerateDialogueResult(BaseModel):
    attachment_id: str
    name: str
    content: str
    content_type: str
    output_format: str
    model: str
    turn_count: int
    voices: list[DialogueVoice]


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


def _with_audio_tag(*, text: str, instructions: str) -> str:
    text = (text or "").strip()
    if not text:
        raise ValueError("Each dialogue turn requires text")

    instructions = (instructions or "").strip()
    if not instructions:
        return text
    if instructions.startswith("[") and instructions.endswith("]"):
        return f"{instructions} {text}"
    return f"[{instructions}] {text}"


def _generate_dialogue_impl(
    *,
    turns: list[DialogueTurn],
    seed: int | None,
    conversation_id: str,
    user_id: int | None,
    agent_slug: str | None,
) -> GenerateDialogueResult:
    from django.contrib.auth.models import User

    from api.authenticate.services import FeatureFlagService
    from api.ai_layers.tools.embedded_channels import conversation_uses_capability_gated_media_tools
    from api.ai_layers.models import Agent
    from api.messaging.models import Conversation, MessageAttachment

    try:
        conversation = Conversation.objects.select_related("organization", "chat_widget").get(
            id=conversation_id
        )
    except Conversation.DoesNotExist as exc:
        raise ValueError("Conversation not found") from exc

    user = User.objects.filter(id=user_id).first() if user_id is not None else None

    if not conversation_uses_capability_gated_media_tools(conversation):
        enabled, _reason = FeatureFlagService.is_feature_enabled(
            "chat-generate-speech",
            organization=getattr(conversation, "organization", None),
            user=user,
        )
        if not enabled:
            raise ValueError("The 'chat-generate-speech' feature is not enabled.")

    agent = (
        Agent.objects.select_related("default_voice", "organization").filter(slug=agent_slug).first()
        if agent_slug
        else None
    )
    organization = _resolve_organization(conversation)
    if organization is None and agent is not None:
        organization = agent.organization
    effective_user = user or getattr(conversation, "user", None)

    inputs: list[dict[str, str]] = []
    voices: list[DialogueVoice] = []
    for index, turn in enumerate(turns, start=1):
        voice = resolve_voice_for_speech(
            voice_id=turn.voice_id,
            agent=agent,
            user=effective_user,
            organization=organization,
        )
        if voice.provider != VoiceProvider.ELEVENLABS:
            raise ValueError(
                f"Dialogue turn {index} requires an ElevenLabs voice. "
                "Call list_voices with target='dialogue' and provide its voice_id."
            )
        text = _with_audio_tag(text=turn.text, instructions=turn.instructions)
        inputs.append({"text": text, "voice_id": voice.provider_voice_id})
        voices.append(DialogueVoice(voice_id=str(voice.id), voice_name=voice.name))

    total_characters = sum(len(item["text"]) for item in inputs)
    if total_characters > MAX_DIALOGUE_CHARACTERS:
        raise ValueError(
            f"Dialogue text is {total_characters} characters; the limit is "
            f"{MAX_DIALOGUE_CHARACTERS}. Split it into smaller dialogues."
        )

    try:
        audio_bytes, model = generate_elevenlabs_dialogue_bytes(inputs=inputs, seed=seed)
    except Exception as exc:
        logger.exception("Failed to generate dialogue with %d turns", len(turns))
        raise ValueError(f"Failed to generate dialogue: {exc}") from exc

    safe_name = slugify(" ".join(item["text"] for item in inputs)[:60]) or "dialogue"
    filename = f"{safe_name}-{uuid.uuid4().hex[:8]}.mp3"
    attachment = MessageAttachment.objects.create(
        conversation=conversation,
        user=user,
        agent=agent,
        kind="file",
        file=ContentFile(audio_bytes, name=filename),
        content_type="audio/mpeg",
        metadata={
            "turns": [
                {
                    "text": item["text"][:2000],
                    "voice_id": voice.voice_id,
                    "voice_name": voice.voice_name,
                }
                for item, voice in zip(inputs, voices, strict=True)
            ],
            "model": model,
            "provider": VoiceProvider.ELEVENLABS,
            "output_format": "mp3_44100_128",
            "seed": seed,
        },
    )
    content_url = attachment.file.url if attachment.file else ""

    return GenerateDialogueResult(
        attachment_id=str(attachment.id),
        name=safe_name,
        content=content_url,
        content_type="audio/mpeg",
        output_format="mp3_44100_128",
        model=model,
        turn_count=len(inputs),
        voices=voices,
    )


def get_tool(
    conversation_id: str | None = None,
    user_id: int | None = None,
    agent_slug: str | None = None,
    **kwargs,
) -> dict:
    if not conversation_id:
        raise ValueError("generate_dialogue requires conversation_id in tool context")

    def generate_dialogue(
        turns: list[DialogueTurn | dict],
        seed: int | None = None,
    ) -> GenerateDialogueResult:
        return _generate_dialogue_impl(
            turns=[DialogueTurn.model_validate(turn) for turn in turns],
            seed=seed,
            conversation_id=conversation_id,
            user_id=user_id,
            agent_slug=agent_slug,
        )

    return {
        "name": "generate_dialogue",
        "description": (
            "Generate one expressive, multi-speaker dialogue audio with ElevenLabs Eleven v3. "
            "Use this instead of create_speech when a script has two or more turns. "
            "Call list_voices with target='dialogue' before choosing voices. "
            "Audio tags such as [whispering], [laughing], or [gentle footsteps] may be "
            "included in turn text; use instructions for a tag that applies at the start "
            "of a turn. The total text across all turns must not exceed 2,000 characters."
        ),
        "parameters": GenerateDialogueParams,
        "function": generate_dialogue,
    }
