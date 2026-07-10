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
ELEVENLABS_DEFAULT_MODEL = "eleven_multilingual_v2"
ELEVENLABS_OUTPUT_FORMAT = "mp3_44100_128"

DEFAULT_VOICE_PREVIEW_TEXT = "Hello! This is a sample of how I sound."
