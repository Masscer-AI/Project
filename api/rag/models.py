from django.db import models
from .managers import chroma_client
from django.utils.text import slugify
from api.ai_layers.models import Agent
import random


def generate_random_name():
    words = [
        "alpha",
        "bravo",
        "charlie",
        "delta",
        "echo",
        "foxtrot",
        "golf",
        "hotel",
        "india",
        "cookie",
        "chroma",
        "happy",
    ]
    return " ".join(random.sample(words, 3))


class Collection(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    chunk_size = models.IntegerField(default=1000)
    chunk_overlap = models.IntegerField(default=100)
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, null=True, blank=True)

    # brief: Which kind of doc
    # tags
    def save(self, *args, **kwargs):
        if not self.name:
            self.name = generate_random_name()

        if not self.slug:
            slug = slugify(self.name)
            self.slug = slug
            chroma_client.get_or_create_collection(collection_name=slug)

        super().save(*args, **kwargs)


class Document(models.Model):
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    text = models.TextField()
    name = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def create_chunks(self):
        chunk_size = self.collection.chunk_size
        chunk_overlap = self.collection.chunk_overlap
        text_length = len(self.text)
        # chunks = []
        i = 0

        while i < text_length:
            chunk_text = self.text[i : i + chunk_size]
            brief_text = chunk_text[:50]
            chunk = Chunk(document=self, content=chunk_text, brief=brief_text)
            chunk.save()
            i += chunk_size - chunk_overlap

        # Chunk.objects.bulk_create(chunks)


class Chunk(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    content = models.TextField()
    brief = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save_in_db(self):
        print("TRYING TP SAVE CHUNK IN CHROMA")
        result = chroma_client.upsert_chunk(
            collection_name=self.document.collection.slug,
            chunk_id=str(self.id),
            chunk_text=self.content,
        )
        print(result, "RESULT FROM SAVING")
