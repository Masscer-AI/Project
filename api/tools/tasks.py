import logging
from celery import shared_task
from .actions import transcribe, generate_video, generate_chunk_video

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
