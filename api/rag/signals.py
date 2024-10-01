# signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Document, Chunk, Collection
from .managers import chroma_client


@receiver(post_save, sender=Document)
def create_chunks_after_save(sender, instance, created, **kwargs):
    print("TRIGGERING POST CREATE FOR DOCUMENT")
    if created:
        instance.create_chunks()


@receiver(post_save, sender=Chunk)
def store_chunk_in_vector_db(sender, instance, created, **kwargs):
    instance.save_in_db()


@receiver(post_delete, sender=Collection)
def collection_deleted(sender, instance, **kwargs):
    collection_name = instance.slug
    chroma_client.delete_collection(collection_name)
