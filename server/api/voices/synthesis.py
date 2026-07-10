from __future__ import annotations

import logging
import os
import time
from typing import Literal

import requests
from django.conf import settings
from elevenlabs.client import ElevenLabs
from elevenlabs.core.api_error import ApiError

from .constants import (
    ELEVENLABS_DEFAULT_MODEL,
    ELEVENLABS_OUTPUT_FORMAT,
    OPENAI_TTS_MODEL,
)
from .models import Voice, VoiceProvider

logger = logging.getLogger(__name__)

OutputFormat = Literal["mp3", "wav"]

_CONCURRENCY_MAX_RETRIES = 5
_CONCURRENCY_BASE_DELAY = 1.0


def synthesize_speech_bytes(
    *,
    voice: Voice,
    text: str,
    instructions: str = "",
    output_format: OutputFormat = "mp3",
) -> tuple[bytes, str]:
    """Return (audio_bytes, model_id_used)."""
    if voice.provider == VoiceProvider.OPENAI:
        model = OPENAI_TTS_MODEL
        merged_instructions = (instructions or "").strip()
        if not merged_instructions and isinstance(voice.metadata, dict):
            merged_instructions = (voice.metadata.get("default_instructions") or "").strip()
        audio = _generate_openai_tts_bytes(
            text=text,
            voice_id=voice.provider_voice_id,
            instructions=merged_instructions,
            output_format=output_format,
        )
        return audio, model

    if voice.provider == VoiceProvider.ELEVENLABS:
        model = ELEVENLABS_DEFAULT_MODEL
        if isinstance(voice.metadata, dict) and voice.metadata.get("model_id"):
            model = str(voice.metadata["model_id"])
        audio = _generate_elevenlabs_tts_bytes(
            text=text,
            voice_id=voice.provider_voice_id,
            model_id=model,
        )
        return audio, model

    raise ValueError(f"Unsupported voice provider: {voice.provider}")


def _generate_openai_tts_bytes(
    *,
    text: str,
    voice_id: str,
    instructions: str,
    output_format: OutputFormat,
) -> bytes:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured")

    payload: dict = {
        "model": OPENAI_TTS_MODEL,
        "input": text,
        "voice": voice_id,
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


def _generate_elevenlabs_tts_bytes(
    *,
    text: str,
    voice_id: str,
    model_id: str,
) -> bytes:
    api_key = getattr(settings, "ELEVENLABS_API_KEY", "") or os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key:
        raise ValueError("ELEVENLABS_API_KEY is not configured")

    client = ElevenLabs(api_key=api_key)
    last_error: ApiError | None = None
    for attempt in range(_CONCURRENCY_MAX_RETRIES):
        try:
            chunks = client.text_to_speech.convert(
                text=text,
                voice_id=voice_id,
                model_id=model_id,
                output_format=ELEVENLABS_OUTPUT_FORMAT,
            )
            return b"".join(chunks)
        except ApiError as exc:
            if exc.status_code != 429:
                raise
            last_error = exc
            if attempt < _CONCURRENCY_MAX_RETRIES - 1:
                delay = _CONCURRENCY_BASE_DELAY * (2**attempt)
                logger.warning(
                    "ElevenLabs 429 concurrency limit; retrying in %.1fs (attempt %d/%d)",
                    delay,
                    attempt + 1,
                    _CONCURRENCY_MAX_RETRIES,
                )
                time.sleep(delay)
    assert last_error is not None
    raise last_error
