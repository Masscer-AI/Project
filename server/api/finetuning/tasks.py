from .actions import start_generator
from celery import shared_task


@shared_task
def async_generate_completions(training_generator_id):
    completions_result = start_generator(training_generator_id)
    return completions_result
