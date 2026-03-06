from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class WinningRates(models.Model):
    name = models.CharField(max_length=255)
    llm_interaction_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=0.15,
    )
    image_generation_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=0.15,
    )
    video_generation_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=0.15,
    )
    speech_synthesis_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=0.15,
    )
    transcription_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=0.15,
    )
    document_generation_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=0.10,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
