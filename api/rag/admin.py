from django.contrib import admin
from .models import Collection, Document, Chunk

@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'chunk_size', 'user', 'created_at')
    search_fields = ('name', 'slug', 'user__username')
    list_filter = ('created_at', 'user')

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('short_text', 'created_at')
    search_fields = ('text',)
    list_filter = ('created_at',)

    def short_text(self, obj):
        return obj.text[:50]
    short_text.short_description = 'Text'

@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = ('document', 'short_text', 'brief', 'created_at')
    search_fields = ('content', 'brief', 'document__text')
    list_filter = ('created_at', 'document')
    def short_text(self, obj):
        return obj.content[:50]
    short_text.short_description = 'Text'