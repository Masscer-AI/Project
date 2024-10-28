from .actions import start_generator
from celery import shared_task


@shared_task
def async_generate_completions(training_generator_id):
    
    start_generator(training_generator_id)
