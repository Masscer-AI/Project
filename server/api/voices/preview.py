from __future__ import annotations

import logging
import os

from django.conf import settings

from .constants import DEFAULT_VOICE_PREVIEW_TEXT
from .models import Voice
from .synthesis import synthesize_speech_bytes

logger = logging.getLogger(__name__)

_PREVIEW_DIR = "voice_previews"


def _preview_sample_text(voice: Voice) -> str:
    if isinstance(voice.metadata, dict):
        custom = (voice.metadata.get("preview_text") or "").strip()
        if custom:
            return custom
    return DEFAULT_VOICE_PREVIEW_TEXT


def _absolute_media_url(relative_url: str) -> str:
    if relative_url.startswith(("http://", "https://")):
        return relative_url
    api_base = (getattr(settings, "API_BASE_URL", None) or "").strip().rstrip("/")
    path = relative_url if relative_url.startswith("/") else f"/{relative_url}"
    if api_base:
        return f"{api_base}{path}"
    return path


def get_or_create_voice_preview_url(*, voice: Voice) -> str:
    """Return a browser-playable URL for a short TTS sample of this voice."""
    relative_path = f"{_PREVIEW_DIR}/{voice.id}.mp3"
    full_path = os.path.join(settings.MEDIA_ROOT, relative_path)
    media_url = settings.MEDIA_URL
    if not media_url.endswith("/"):
        media_url = f"{media_url}/"
    public_relative = f"{media_url}{relative_path}"

    if not os.path.isfile(full_path):
        sample = _preview_sample_text(voice)
        try:
            audio_bytes, _model = synthesize_speech_bytes(
                voice=voice,
                text=sample,
                output_format="mp3",
            )
        except Exception:
            logger.exception("voice preview synthesis failed for voice_id=%s", voice.id)
            raise
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as handle:
            handle.write(audio_bytes)

    return _absolute_media_url(public_relative)
