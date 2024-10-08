from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import TranscriptionJob, VideoGenerationJob, VideoChunk
from .tasks import async_transcribe, async_generate_video, async_generate_chunk_video


@receiver(post_save, sender=TranscriptionJob)
def trigger_async_transcription(sender, instance, created, **kwargs):
    if created:
        print("Triggering a new trascribe action!")
        async_transcribe.delay(instance.id)


@receiver(post_save, sender=VideoGenerationJob)
def trigger_async_generate_video(sender, instance, created, **kwargs):
    if created:
        print("Trying to generate a video!")
        async_generate_video.delay(instance.id)

@receiver(post_save, sender=VideoChunk)
def trigger_async_generate_chunk_video(sender, instance, created, **kwargs):
    if created:
        print("Trying to generate a chunk video!")
        async_generate_chunk_video.delay(instance.id)


