from django.contrib import admin
from .models import AIProvider, AIProviderCredentials, SearchEngineProvider, SearchEngineProviderCredentials, MediaProvider, MediaProviderCredentials

@admin.register(AIProvider)
class AIProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'website_url', 'docs_url', 'created_at', 'updated_at')
    search_fields = ('name',)

@admin.register(AIProviderCredentials)
class ProviderCredentialsAdmin(admin.ModelAdmin):
    list_display = ('provider', 'user', 'api_key', 'created_at', 'updated_at')
    search_fields = ('provider__name', 'user__username')
    list_filter = ('provider', 'user')

@admin.register(SearchEngineProvider)
class SearchEngineProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'website_url', 'docs_url', 'created_at', 'updated_at')
    search_fields = ('name',)

@admin.register(SearchEngineProviderCredentials)
class SearchEngineProviderCredentialsAdmin(admin.ModelAdmin):
    list_display = ('provider', 'api_key', 'created_at', 'updated_at')
    search_fields = ('provider__name',)
    list_filter = ('provider',)

@admin.register(MediaProvider)
class MediaProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'website_url', 'docs_url', 'created_at', 'updated_at')
    search_fields = ('name',)

@admin.register(MediaProviderCredentials)
class MediaProviderCredentialsAdmin(admin.ModelAdmin):
    list_display = ('provider', 'api_key', 'created_at', 'updated_at')
    search_fields = ('provider__name',)
    list_filter = ('provider',)
