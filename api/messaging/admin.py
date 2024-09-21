from django.contrib import admin
from .models import Conversation, Message

class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'title', 'created_at', 'updated_at')
    list_filter = ('user', 'created_at', 'updated_at')
    search_fields = ('title', 'user__username')
    ordering = ('-created_at',)

class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'type', 'text', 'created_at', 'updated_at')
    list_filter = ('type', 'created_at', 'updated_at')
    search_fields = ('text', 'conversation__title')
    ordering = ('-created_at',)

admin.site.register(Conversation, ConversationAdmin)
admin.site.register(Message, MessageAdmin)
