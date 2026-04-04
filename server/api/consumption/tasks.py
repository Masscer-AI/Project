from .actions import register_llm_interaction, register_image_generation
from celery import shared_task


@shared_task
def async_register_llm_interaction(user_id, input_tokens, output_tokens, model_slug, organization_id=None):
    return register_llm_interaction(user_id, input_tokens, output_tokens, model_slug, organization_id)


@shared_task
def async_register_image_generation(user_id, model_slug, organization_id=None):
    return register_image_generation(user_id, model_slug, organization_id)
