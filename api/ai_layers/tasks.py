# import logging
from celery import shared_task
from .actions import generate_agent_profile_picture

# logger = logging.getLogger(__name__)


@shared_task
def async_generate_agent_profile_picture(agent_id: int):   
    return generate_agent_profile_picture(agent_id)


