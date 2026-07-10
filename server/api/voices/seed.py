from __future__ import annotations

from dataclasses import dataclass, field

from api.voices.constants import SYSTEM_ELEVENLABS_VOICES, SYSTEM_OPENAI_VOICES
from api.voices.models import Voice, VoiceProvider, VoiceScope


@dataclass(frozen=True)
class SystemVoiceSeed:
    provider: str
    slug: str
    name: str
    provider_voice_id: str
    metadata: dict = field(default_factory=dict)


def build_system_voice_seeds() -> list[SystemVoiceSeed]:
    seeds: list[SystemVoiceSeed] = []
    for provider_voice_id, name in SYSTEM_OPENAI_VOICES:
        seeds.append(
            SystemVoiceSeed(
                provider=VoiceProvider.OPENAI,
                slug=provider_voice_id,
                name=name,
                provider_voice_id=provider_voice_id,
            )
        )
    for entry in SYSTEM_ELEVENLABS_VOICES:
        seeds.append(
            SystemVoiceSeed(
                provider=VoiceProvider.ELEVENLABS,
                slug=entry["slug"],
                name=entry["name"],
                provider_voice_id=entry["provider_voice_id"],
                metadata=dict(entry.get("metadata") or {}),
            )
        )
    return seeds


def sync_system_voices(*, dry_run: bool = False) -> tuple[list[str], list[str], list[str]]:
    """Upsert system voices from constants. Returns (created, updated, unchanged) slugs."""
    created: list[str] = []
    updated: list[str] = []
    unchanged: list[str] = []

    seeds = build_system_voice_seeds()
    seeded_elevenlabs_ids = {
        s.provider_voice_id
        for s in seeds
        if s.provider == VoiceProvider.ELEVENLABS
    }

    for seed in seeds:
        lookup = {
            "scope": VoiceScope.SYSTEM,
            "provider": seed.provider,
            "provider_voice_id": seed.provider_voice_id,
            "user": None,
            "organization": None,
        }
        defaults = {
            "name": seed.name,
            "slug": seed.slug,
            "is_active": True,
            "metadata": seed.metadata,
        }

        if dry_run:
            if Voice.objects.filter(**lookup).exists():
                unchanged.append(seed.slug)
            else:
                created.append(seed.slug)
            continue

        voice, was_created = Voice.objects.get_or_create(**lookup, defaults=defaults)
        if was_created:
            created.append(seed.slug)
            continue

        changed_fields: list[str] = []
        for field_name, value in defaults.items():
            if getattr(voice, field_name) != value:
                setattr(voice, field_name, value)
                changed_fields.append(field_name)

        if changed_fields:
            voice.save(update_fields=changed_fields)
            updated.append(seed.slug)
        else:
            unchanged.append(seed.slug)

    stale = Voice.objects.filter(
        scope=VoiceScope.SYSTEM,
        provider=VoiceProvider.ELEVENLABS,
        is_active=True,
    ).exclude(provider_voice_id__in=seeded_elevenlabs_ids)
    if not dry_run:
        stale.update(is_active=False)

    return created, updated, unchanged
