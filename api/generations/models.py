from django.db import models
from django.contrib.auth.models import User
import uuid
import os
from django.conf import settings

SAVE_PATH = os.path.join(settings.MEDIA_ROOT, "generations/videos")
os.makedirs(SAVE_PATH, exist_ok=True)


class VideoGeneration(models.Model):
    ENGINE_CHOICES = [
        ("runway", "Runway"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, null=True, blank=True)
    prompt = models.TextField()
    message_id = models.CharField(max_length=255)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ratio = models.CharField(max_length=255)
    engine = models.CharField(max_length=255, choices=ENGINE_CHOICES, default="runway")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    file = models.FileField(upload_to="generations/videos", null=True, blank=True)

    def __str__(self):
        return self.name


class AudioGeneration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    text = models.TextField()
    voice = models.CharField(max_length=255)
    provider = models.CharField(max_length=255)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    file = models.FileField(upload_to="generations/audios", null=True, blank=True)

    def __str__(self):
        return self.text
