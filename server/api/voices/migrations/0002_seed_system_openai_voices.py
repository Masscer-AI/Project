from django.db import migrations

from api.voices.constants import SYSTEM_OPENAI_VOICES
from api.voices.models import VoiceProvider, VoiceScope


def seed_system_openai_voices(apps, schema_editor):
    Voice = apps.get_model("voices", "Voice")
    for provider_voice_id, name in SYSTEM_OPENAI_VOICES:
        Voice.objects.get_or_create(
            scope=VoiceScope.SYSTEM,
            provider=VoiceProvider.OPENAI,
            provider_voice_id=provider_voice_id,
            defaults={
                "name": name,
                "slug": provider_voice_id,
                "user": None,
                "organization": None,
                "is_active": True,
                "metadata": {},
            },
        )


def unseed_system_openai_voices(apps, schema_editor):
    Voice = apps.get_model("voices", "Voice")
    provider_ids = [v[0] for v in SYSTEM_OPENAI_VOICES]
    Voice.objects.filter(
        scope=VoiceScope.SYSTEM,
        provider=VoiceProvider.OPENAI,
        provider_voice_id__in=provider_ids,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("voices", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_system_openai_voices, unseed_system_openai_voices),
    ]
