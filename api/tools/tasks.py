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
    logger.info(f"Initializing task to transcribe: {transcribe_job_id}")
    return transcribe(transcribe_job_id)


@shared_task
def async_generate_video(video_job_id: int):
    logger.info(f"Initializing task to generate a video: {video_job_id}")
    return generate_video(video_job_id)


@shared_task
def async_generate_chunk_video(video_chunk_id: int):
    logger.info(f"Initializing task to generate a chunk video: {video_chunk_id}")
    return generate_chunk_video(video_chunk_id)


@shared_task
def async_image_to_video(prompt_image_b64, prompt_text, ratio, user_id, message_id):
    return generate_video_from_image(
        prompt_image_b64, prompt_text, user_id, "runway", message_id, ratio
    )
