from __future__ import annotations

import uuid

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models


class VoiceScope(models.TextChoices):
    SYSTEM = "system", "System"
    ORGANIZATION = "organization", "Organization"
    USER = "user", "User"


class VoiceProvider(models.TextChoices):
    OPENAI = "openai", "OpenAI"
    ELEVENLABS = "elevenlabs", "ElevenLabs"


class Voice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100)
    provider = models.CharField(max_length=32, choices=VoiceProvider.choices)
    provider_voice_id = models.CharField(max_length=255)
    scope = models.CharField(max_length=32, choices=VoiceScope.choices)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="catalog_voices",
    )
    organization = models.ForeignKey(
        "authenticate.Organization",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="voices",
    )
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["scope", "organization", "user", "provider", "provider_voice_id"],
                name="voices_voice_unique_per_scope_owner",
            ),
        ]
        ordering = ["scope", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.provider})"

    def clean(self) -> None:
        if self.scope == VoiceScope.SYSTEM:
            if self.user_id is not None or self.organization_id is not None:
                raise ValidationError("System voices must not have an owner.")
        elif self.scope == VoiceScope.ORGANIZATION:
            if self.organization_id is None or self.user_id is not None:
                raise ValidationError("Organization voices require organization and no user.")
        elif self.scope == VoiceScope.USER:
            if self.user_id is None:
                raise ValidationError("User voices require a user.")
        else:
            raise ValidationError(f"Unknown scope: {self.scope}")

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)
