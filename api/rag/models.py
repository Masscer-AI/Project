from django.db import models
from .managers import chroma_client
from django.utils.text import slugify
from api.ai_layers.models import Agent
from api.messaging.models import Conversation
import random


def generate_random_name():
    words = [
        "apple",
        "banana",
        "cherry",
        "dragon",
        "elephant",
        "flamingo",
        "giraffe",
        "honey",
        "iguana",
        "jelly",
        "kite",
        "lemon",
        "mango",
        "nebula",
        "octopus",
        "pineapple",
        "quokka",
        "raspberry",
        "starfish",
        "tiger",
        "umbrella",
        "violin",
        "watermelon",
        "xylophone",
        "yogurt",
        "zebra",
        "acorn",
        "balloon",
        "cactus",
        "daffodil",
        "echo",
        "feather",
        "galaxy",
        "hammock",
        "island",
        "jigsaw",
        "kaleidoscope",
        "lantern",
        "meadow",
        "notebook",
        "olive",
        "pebble",
        "quilt",
        "river",
        "snowflake",
        "tambourine",
        "unicorn",
        "volcano",
        "willow",
        "xerus",
    ]

    return " ".join(random.sample(words, 3))


class Collection(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    chunk_size = models.IntegerField(default=2000)
    chunk_overlap = models.IntegerField(default=200)
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, null=True, blank=True)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, null=True, blank=True
    )

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
    brief = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Document(name={self.name},id={self.id})"

    def create_chunks(self):
        from .signals import chunks_created

        chunk_size = self.collection.chunk_size
        chunk_overlap = self.collection.chunk_overlap
        text_length = len(self.text)
        i = 0
        chunks = []

        while i < text_length:
            chunk_text = self.text[i : i + chunk_size]
            chunk = Chunk(document=self, content=chunk_text)
            chunks.append(chunk)
            i += chunk_size - chunk_overlap

        Chunk.objects.bulk_create(chunks)
        chunks_created.send(sender=self)


class Chunk(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    content = models.TextField()
    brief = models.TextField(blank=True, null=True)
    tags = models.CharField(blank=True, null=True, max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def save_in_db(self):
        if self.brief:
            brief = self.brief
        else:
            brief = self.content
        chroma_client.upsert_chunk(
            collection_name=self.document.collection.slug,
            chunk_id=str(self.id+"-brief"),
            chunk_text=brief,
            metadata={
                "document_id": f"{self.document.id}",
                "content": self.content,
                "chunk_id": self.id,
                "tags": self.tags,
            },
        )
