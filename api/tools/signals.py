from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import TranscriptionJob  
from .tasks import async_transcribe  

@receiver(post_save, sender=TranscriptionJob)
def trigger_async_transcription(sender, instance, created, **kwargs):
    if created:
        print("Triggering a new trascribe action!")
        async_transcribe.delay(instance.id)
