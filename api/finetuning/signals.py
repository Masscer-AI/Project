# Create a new signal called: "completions_generated"
from django.dispatch import receiver, Signal
from api.utils.color_printer import printer

completions_generated = Signal()


@receiver(completions_generated)
def completions_generated_handler(sender, **kwargs):
    printer.yellow("COMPLETIONS GENERATED, TIME TO SAVE THEM IN RAG")
    # completions = kwargs.get("completions")
    # for completion in completions:
    #     completion.training_generator.status = TrainingGenerator.COMPLETED
    #     completion.training_generator.save()
