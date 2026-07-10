from __future__ import annotations

from django.contrib.auth.models import User

from api.authenticate.models import Organization
from api.messaging.models import Conversation

from .access import resolve_accessible_voices


def _resolve_organization(conversation: Conversation, agent) -> Organization | None:
    organization = getattr(conversation, "organization", None) or getattr(
        agent, "organization", None
    )
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


def build_create_speech_tool_instructions(
    *,
    conversation: Conversation,
    agent,
    user: User | None,
) -> str:
    organization = _resolve_organization(conversation, agent)
    voices = list(resolve_accessible_voices(user=user, organization=organization))

    lines = [
        "\n\nSpeech generation is enabled.",
        "If the user asks for an audio version, call create_speech(text, voice_id, instructions, output_format).",
        "voice_id must be a UUID from the available voices list below.",
        "output_format must be mp3 or wav.",
        "The instructions parameter controls accent, tone, speed, etc. (OpenAI voices only).",
        "\nAvailable voices:",
    ]
    for v in voices:
        lines.append(f"- {v.name} ({v.provider}, voice_id={v.id})")

    default_voice = getattr(agent, "default_voice", None) if agent else None
    if default_voice is not None and default_voice.is_active:
        lines.append(f"\nDefault voice for this agent: {default_voice.name} (voice_id={default_voice.id}).")
    else:
        lines.append("\nIf voice_id is omitted, the system default voice is used.")

    lines.append(
        "\nWhen referencing the audio attachment in markdown, link it like: "
        "[Listen](attachment:<attachment_id>)."
    )
    return "".join(lines)
