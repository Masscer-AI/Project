from django.contrib import admin
from .models import Agent, LanguageModel


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "user", "is_public")
    search_fields = ("name", "slug", "user__username")


@admin.register(LanguageModel)
class LanguageModelAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "provider", "created_at", "updated_at")
    search_fields = ("name", "slug", "provider__name")
