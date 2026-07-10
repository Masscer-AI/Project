"""Built-in OpenAI voices for gpt-4o-mini-tts (system catalog seeds)."""

SYSTEM_OPENAI_VOICES: list[tuple[str, str]] = [
    ("alloy", "Alloy"),
    ("ash", "Ash"),
    ("ballad", "Ballad"),
    ("coral", "Coral"),
    ("echo", "Echo"),
    ("fable", "Fable"),
    ("nova", "Nova"),
    ("onyx", "Onyx"),
    ("sage", "Sage"),
    ("shimmer", "Shimmer"),
    ("verse", "Verse"),
    ("marin", "Marin"),
    ("cedar", "Cedar"),
]

DEFAULT_OPENAI_VOICE_ID = "coral"

OPENAI_TTS_MODEL = "gpt-4o-mini-tts"
# ELEVENLABS_DEFAULT_MODEL = "eleven_multilingual_v2"
ELEVENLABS_DEFAULT_MODEL = "eleven_flash_v2_5"
ELEVENLABS_OUTPUT_FORMAT = "mp3_44100_128"

DEFAULT_VOICE_PREVIEW_TEXT = "Hello! This is a sample of how I sound."

# Curated ElevenLabs premade voices (system catalog).
SYSTEM_ELEVENLABS_VOICES: list[dict] = [
    {
        "slug": "bella",
        "name": "Bella",
        "provider_voice_id": "hpp4J3VqNfWAUOO0d1Us",
        "metadata": {"model_id": ELEVENLABS_DEFAULT_MODEL},
    },
    {
        "slug": "roger",
        "name": "Roger",
        "provider_voice_id": "CwhRBWXzGAHq8TQ4Fs17",
        "metadata": {"model_id": ELEVENLABS_DEFAULT_MODEL},
    },
    {
        "slug": "sarah",
        "name": "Sarah",
        "provider_voice_id": "EXAVITQu4vr4xnSDxMaL",
        "metadata": {"model_id": ELEVENLABS_DEFAULT_MODEL},
    },
    {
        "slug": "laura",
        "name": "Laura",
        "provider_voice_id": "FGY2WhTYpPnrIDTdsKH5",
        "metadata": {"model_id": ELEVENLABS_DEFAULT_MODEL},
    },
    {
        "slug": "charlie",
        "name": "Charlie",
        "provider_voice_id": "IKne3meq5aSn9XLyUdCD",
        "metadata": {"model_id": ELEVENLABS_DEFAULT_MODEL},
    },
    {
        "slug": "george",
        "name": "George",
        "provider_voice_id": "JBFqnCBsd6RMkjVDRZzb",
        "metadata": {"model_id": ELEVENLABS_DEFAULT_MODEL},
    },
    {
        "slug": "callum",
        "name": "Callum",
        "provider_voice_id": "N2lVS1w4EtoT3dr4eOWO",
        "metadata": {"model_id": ELEVENLABS_DEFAULT_MODEL},
    },
]
