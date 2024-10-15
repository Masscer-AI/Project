import logging
from celery import shared_task
from .actions import generate_chunk_brief, generate_document_brief

logger = logging.getLogger(__name__)


@shared_task
def async_generate_chunk_brief(chunk_id: int):
    return generate_chunk_brief(chunk_id)

@shared_task
def async_generate_document_brief(document_id: int):
    return generate_document_brief(document_id)
