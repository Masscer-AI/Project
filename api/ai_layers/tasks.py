# import logging
from celery import shared_task
from .actions import generate_agent_profile_picture


@shared_task
def async_generate_agent_profile_picture(agent_id: int):
    result = generate_agent_profile_picture(agent_id)
    return result
