from .actions import register_llm_interaction
from celery import shared_task


@shared_task
def async_register_llm_interaction(user_id, input_tokens, output_tokens, model_slug):
    print("registering llm interaction for user ", user_id)
    return register_llm_interaction(user_id, input_tokens, output_tokens, model_slug)
