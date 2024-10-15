# signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver, Signal
from .models import Document, Chunk, Collection
from .managers import chroma_client
from .tasks import async_generate_chunk_brief, async_generate_document_brief

chunks_created = Signal()


@receiver(post_save, sender=Document)
def create_chunks_after_save(sender, instance, created, **kwargs):
    if created:
        async_generate_document_brief.delay(instance.pk)
        instance.create_chunks()


@receiver(post_save, sender=Chunk)
def store_chunk_in_vector_db(sender, instance, created, **kwargs):
    instance.save_in_db()


@receiver(post_delete, sender=Collection)
def collection_deleted(sender, instance, **kwargs):
    collection_name = instance.slug
    chroma_client.delete_collection(collection_name)


@receiver(chunks_created)
def chunks_created_handler(sender, **kwargs):
    chunks = Chunk.objects.filter(document=sender)

    chunks_text = []
    chunks_ids = []
    chunks_metadatas = []
    for c in chunks:
        chunks_text.append(c.content)
        chunks_ids.append(str(c.id))
        chunks_metadatas.append(
            {"document_id": str(sender.id), "content": c.content, "chunk_id": c.id}
        )

    chroma_client.bulk_upsert_chunks(
        sender.collection.slug,
        documents=chunks_text,
        chunk_ids=chunks_ids,
        metadatas=chunks_metadatas,
    )

    for c in chunks:
        async_generate_chunk_brief.delay(c.id)
