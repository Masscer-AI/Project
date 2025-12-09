from django.contrib import admin
from django.utils.html import format_html
from django.conf import settings
from .models import (
    Conversation,
    Message,
    ChatWidget,
    ConversationAlertRule,
    ConversationAlert,
    AlertSubscription,
)


class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "created_at", "updated_at")
    list_filter = ("user", "created_at", "updated_at")
    search_fields = ("title", "user__username")
    ordering = ("-created_at",)


class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "short_text",
        "type",
        "conversation",
        "created_at",
    )
    list_filter = ("type", "created_at", "updated_at", "conversation")
    search_fields = ("text", "conversation__title")
    ordering = ("-created_at",)

    def short_text(self, obj):
        return obj.text[:30]  # Return the first 30 characters

    short_text.short_description = "Message Text"


class ChatWidgetAdmin(admin.ModelAdmin):
    list_display = ("name", "token", "agent", "enabled", "created_by", "created_at")
    list_filter = ("enabled", "web_search_enabled", "rag_enabled", "created_at", "agent")
    search_fields = ("name", "token", "agent__name", "agent__slug")
    readonly_fields = ("token", "widget_script_url", "created_at", "updated_at")
    fields = (
        "name",
        "token",
        "widget_script_url",
        "enabled",
        "agent",
        "web_search_enabled",
        "rag_enabled",
        "plugins_enabled",
        "created_by",
        "created_at",
        "updated_at",
    )

    def widget_script_url(self, obj):
        if not obj.token:
            return "Token will be generated after saving"
        
        # Get the base URL from settings or use a default
        # The widget is served from the streaming server, not the API server
        base_url = getattr(settings, "STREAMING_SERVER_URL", "http://localhost:8001")
        script_url = f"{base_url}/widget/{obj.token}.js"
        script_tag = f'<script src="{script_url}"></script>'
        
        return format_html(
            '<div style="margin: 10px 0;">'
            '<input type="text" id="widget-script-{0}" value="{1}" readonly style="width: 100%; padding: 5px; font-family: monospace; margin-bottom: 5px;">'
            '<button type="button" onclick="navigator.clipboard.writeText(document.getElementById(\'widget-script-{0}\').value); alert(\'Copied to clipboard!\');" style="padding: 5px 10px; cursor: pointer;">Copy Script Tag</button>'
            '</div>',
            obj.id,
            script_tag
        )
    
    widget_script_url.short_description = "Widget Script URL"


class ConversationAlertRuleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "organization",
        "scope",
        "enabled",
        "notify_to",
        "created_by",
        "created_at",
    )
    list_filter = ("enabled", "scope", "notify_to", "organization", "created_at")
    search_fields = ("name", "trigger", "organization__name", "created_by__username")
    filter_horizontal = ("agents", "selected_members")
    readonly_fields = ("id", "created_at", "updated_at")
    fields = (
        "id",
        "name",
        "trigger",
        "extractions",
        "scope",
        "enabled",
        "notify_to",
        "organization",
        "created_by",
        "agents",
        "selected_members",
        "created_at",
        "updated_at",
    )


class ConversationAlertAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "alert_rule",
        "conversation",
        "status",
        "resolved_by",
        "dismissed_by",
        "created_at",
    )
    list_filter = ("status", "alert_rule", "created_at", "updated_at")
    search_fields = (
        "title",
        "reasoning",
        "alert_rule__name",
        "conversation__title",
        "conversation__id",
    )
    readonly_fields = ("id", "created_at", "updated_at")
    fields = (
        "id",
        "title",
        "reasoning",
        "extractions",
        "status",
        "conversation",
        "alert_rule",
        "resolved_by",
        "dismissed_by",
        "created_at",
        "updated_at",
    )


class AlertSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "alert_rule", "created_at")
    list_filter = ("alert_rule", "created_at")
    search_fields = (
        "user__username",
        "user__email",
        "alert_rule__name",
        "alert_rule__organization__name",
    )
    readonly_fields = ("id", "created_at", "updated_at")
    fields = ("id", "user", "alert_rule", "created_at", "updated_at")


admin.site.register(Conversation, ConversationAdmin)
admin.site.register(Message, MessageAdmin)
admin.site.register(ChatWidget, ChatWidgetAdmin)
admin.site.register(ConversationAlertRule, ConversationAlertRuleAdmin)
admin.site.register(ConversationAlert, ConversationAlertAdmin)
admin.site.register(AlertSubscription, AlertSubscriptionAdmin)
