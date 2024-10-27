from django.contrib import admin
from .models import WSConversation, WSMessage, WSNumber
from .actions import generate_conversation_context


@admin.register(WSConversation)
class WSConversationAdmin(admin.ModelAdmin):
    list_display = ("title", "summary", "sentiment", "user_number", "ai_number", "status", "created_at", "updated_at")
    search_fields = ("user_number", "ai_number__number")
    list_filter = ("status", "created_at")
    actions = ["_generate_conversation_context"]

    def _generate_conversation_context(self, request, queryset):
        for conversation in queryset:
            generate_conversation_context(conversation.id)


@admin.register(WSMessage)
class WSMessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "message_type", "created_at", "updated_at")
    search_fields = ("content", "conversation__user_number")
    list_filter = ("message_type", "created_at")


@admin.register(WSNumber)
class WhatsAppNumberAdmin(admin.ModelAdmin):
    list_display = ("user", "number", "verified", "created_at", "updated_at")
    search_fields = ("user__username", "number")
    list_filter = ("verified", "created_at")
