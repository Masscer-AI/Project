from django.contrib import admin
from .models import Collection, Document, Chunk
from .actions import generate_chunk_brief, generate_document_brief
from .tasks import async_generate_chunk_brief


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "chunk_size", "user", "created_at")
    search_fields = ("name", "slug", "user__username")
    list_filter = ("created_at", "user")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "brief", "short_text", "created_at")
    search_fields = ("text",)
    list_filter = ("created_at",)
    actions = ["generate_brief"]

    def short_text(self, obj):
        return obj.text[:50]

    def generate_brief(self, request, queryset):
        for c in queryset:
            generate_document_brief(c.id)

    short_text.short_description = "Text"


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = ("id", "brief", "tags", "document", "created_at")
    search_fields = ("content", "brief", "document__text")
    list_filter = ("created_at", "document")
    actions = ["generate_brief", "async_generate_brief"]

    def short_text(self, obj):
        return obj.content[:50]

    def generate_brief(self, request, queryset):
        for c in queryset:
            generate_chunk_brief(c.id)

    def async_generate_brief(self, request, queryset):
        for c in queryset:
            async_generate_chunk_brief.delay(c.id)

    short_text.short_description = "Text"
