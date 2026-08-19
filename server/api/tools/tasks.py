import logging
from celery import shared_task
from .actions import (
    transcribe,
    generate_video,
    generate_chunk_video,
    generate_video_from_image,
)

logger = logging.getLogger(__name__)


@shared_task
def async_transcribe(transcribe_job_id: int):
    transcription_result = transcribe(transcribe_job_id)
    return transcription_result


@shared_task
def async_generate_video(video_job_id: int):
    video_result = generate_video(video_job_id)
    return video_result


@shared_task
def async_generate_chunk_video(video_chunk_id: int):
    chunk_video_result = generate_chunk_video(video_chunk_id)
    return chunk_video_result


@shared_task
def async_image_to_video(prompt_image_b64, prompt_text, ratio, user_id, message_id):
    image_to_video_result = generate_video_from_image(
        prompt_image_b64, prompt_text, ratio, user_id, "runway", message_id
    )
    return image_to_video_result


@shared_task
def async_audio_generation(text, voice, user_id, message_id):
    audio_result = generate_audio(text, voice, user_id, message_id)
    return audio_result
