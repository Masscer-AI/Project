from django.contrib import admin
from .models import Agent, ModelConfig

@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'user', 'is_public')
    search_fields = ('name', 'slug', 'user__username')

@admin.register(ModelConfig)
class ModelConfigAdmin(admin.ModelAdmin):
    list_display = ('temperature', 'max_tokens', 'top_p', 'frequency_penalty', 'presence_penalty')
    search_fields = ('temperature', 'max_tokens')
