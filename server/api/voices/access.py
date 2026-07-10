from __future__ import annotations

from django.contrib.auth.models import User
from django.db.models import Q, QuerySet

from api.authenticate.models import Organization

from .constants import DEFAULT_OPENAI_VOICE_ID
from .models import Voice, VoiceProvider, VoiceScope


def resolve_accessible_voices(
    *,
    user: User | None = None,
    organization: Organization | None = None,
) -> QuerySet[Voice]:
    q = Q(scope=VoiceScope.SYSTEM, is_active=True)
    if organization is not None:
        q |= Q(
            scope=VoiceScope.ORGANIZATION,
            organization=organization,
            is_active=True,
        )
    if user is not None:
        q |= Q(scope=VoiceScope.USER, user=user, is_active=True)
    return Voice.objects.filter(q).order_by("scope", "name")


def voice_is_accessible(
    voice: Voice,
    *,
    user: User | None = None,
    organization: Organization | None = None,
) -> bool:
    if not voice.is_active:
        return False
    if voice.scope == VoiceScope.SYSTEM:
        return True
    if voice.scope == VoiceScope.ORGANIZATION:
        return organization is not None and voice.organization_id == organization.id
    if voice.scope == VoiceScope.USER:
        return user is not None and voice.user_id == user.id
    return False


def get_voice_by_id(
    voice_id: str,
    *,
    user: User | None = None,
    organization: Organization | None = None,
) -> Voice:
    try:
        voice = Voice.objects.get(pk=voice_id, is_active=True)
    except Voice.DoesNotExist as exc:
        raise ValueError(f"Voice not found: {voice_id}") from exc
    if not voice_is_accessible(voice, user=user, organization=organization):
        raise ValueError(f"Voice not accessible: {voice_id}")
    return voice


def get_system_voice_by_provider_id(provider_voice_id: str) -> Voice | None:
    return Voice.objects.filter(
        scope=VoiceScope.SYSTEM,
        provider=VoiceProvider.OPENAI,
        provider_voice_id=provider_voice_id,
        is_active=True,
    ).first()


def get_default_system_voice() -> Voice:
    voice = get_system_voice_by_provider_id(DEFAULT_OPENAI_VOICE_ID)
    if voice is None:
        raise RuntimeError(
            f"Default system voice '{DEFAULT_OPENAI_VOICE_ID}' is not seeded. Run migrations."
        )
    return voice


def resolve_voice_for_speech(
    *,
    voice_id: str | None,
    agent,
    user: User | None = None,
    organization: Organization | None = None,
) -> Voice:
    if voice_id:
        return get_voice_by_id(voice_id, user=user, organization=organization)

    default_voice = getattr(agent, "default_voice", None) if agent else None
    if default_voice is not None and default_voice.is_active:
        if voice_is_accessible(default_voice, user=user, organization=organization):
            return default_voice

    return get_default_system_voice()
