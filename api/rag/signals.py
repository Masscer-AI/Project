# signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Document, Chunk


@receiver(post_save, sender=Document)
def create_chunks_after_save(sender, instance, created, **kwargs):
    print("TRIGGERING POST CREATE FOR DOCUMENT")
    if created:
        instance.create_chunks()


@receiver(post_save, sender=Chunk)
def store_chunk_in_vector_db(sender, instance, created, **kwargs):
    print("Triggering post save for chunk")
    instance.save_in_db()
