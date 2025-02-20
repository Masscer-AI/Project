# Create a new signal called: "completions_generated"
from django.dispatch import receiver, Signal
from api.utils.color_printer import printer
from django.db.models.signals import post_save
from .models import TrainingGenerator, Completion
from .tasks import async_generate_completions

completions_generated = Signal()


@receiver(post_save, sender=TrainingGenerator)
def training_generator_post_save_handler(sender, **kwargs):
    async_generate_completions.delay(kwargs.get("instance").id)


@receiver(completions_generated)
def completions_generated_handler(sender, **kwargs):
    printer.yellow("COMPLETIONS GENERATED, TIME TO SAVE THEM IN RAG")


@receiver(post_save, sender=Completion)
def completion_post_save_handler(sender, **kwargs):
    completion = kwargs.get("instance")
    printer.yellow(f"COMPLETION {completion.id} POST SAVE HANDLER")
    if completion.approved:
        printer.success(f"COMPLETION {completion.id} IS APPROVED, SAVING IN MEMORY")
        completion.save_in_memory()
    else:
        printer.yellow(
            f"COMPLETION {completion.id} IS NOT APPROVED, REMOVING FROM MEMORY"
        )
        completion.remove_from_memory()


