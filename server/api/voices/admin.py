from django.contrib import admin

from .models import Voice


@admin.register(Voice)
class VoiceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "provider", "scope", "is_active", "created_at")
    list_filter = ("provider", "scope", "is_active")
    search_fields = ("name", "slug", "provider_voice_id")
    readonly_fields = ("id", "created_at", "updated_at")
