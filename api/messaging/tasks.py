import logging
from celery import shared_task
from .actions import generate_conversation_title

logger = logging.getLogger(__name__)


@shared_task
def async_generate_conversation_title(conversation_id: str):
    result = generate_conversation_title(conversation_id=conversation_id)
    return result
