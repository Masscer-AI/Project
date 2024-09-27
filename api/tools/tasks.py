import logging
from celery import shared_task
from .actions import transcribe

logger = logging.getLogger(__name__)


@shared_task
def async_transcribe(transcribe_job_id: int):
    logger.info(f"Initializing task to transcribe: {transcribe_job_id}")
    return transcribe(transcribe_job_id)
