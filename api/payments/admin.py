from django.contrib import admin
from .models import WinningRates


@admin.register(WinningRates)
class WinningRatesAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "llm_interaction_rate",
        "image_generation_rate",
        "video_generation_rate",
        "speech_synthesis_rate",
        "transcription_rate",
        "document_generation_usd",
    ]
