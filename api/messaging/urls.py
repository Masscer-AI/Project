from django.urls import path
from .views import (
    ConversationView,
    ConversationBulkView,
    MessageView,
    upload_audio,
    upload_message_attachments,
    link_message_attachment,
    get_suggestion,
    SharedConversationView,
    ChatWidgetConfigView,
    ChatWidgetSessionView,
    ChatWidgetConversationView,
    ChatWidgetAgentTaskView,
    ChatWidgetSocketAuthView,
    ChatWidgetView,
    ConversationAlertView,
    ConversationAlertStatsView,
    ConversationAlertRuleView,
    TagView,
)

app_name = "messaging"

urlpatterns = [
    path("conversations", ConversationView.as_view(), name="conversation_list"),
    path("conversations/bulk/", ConversationBulkView.as_view(), name="conversation_bulk"),
    path(
        "conversations/<uuid:id>/",
        ConversationView.as_view(),
        name="conversation_detail",
    ),
    path("messages", MessageView.as_view(), name="message_list"),
    path("messages/<int:id>/", MessageView.as_view(), name="message_detail"),
    path("upload-audio/", upload_audio, name="upload_audio"),
    path("attachments/upload/", upload_message_attachments, name="upload_message_attachments"),
    path("attachments/link/", link_message_attachment, name="link_message_attachment"),
    path("get-suggestion/", get_suggestion, name="get_suggestion"),
    path(
        "shared-conversations/",
        SharedConversationView.as_view(),
        name="shared_conversation_list",
    ),
    path(
        "shared-conversations/<uuid:share_id>/",
        SharedConversationView.as_view(),
        name="shared_conversation_detail",
    ),
    path(
        "widgets/<str:token>/config/",
        ChatWidgetConfigView.as_view(),
        name="widget_config",
    ),
    path(
        "widgets/<str:token>/session/",
        ChatWidgetSessionView.as_view(),
        name="widget_session",
    ),
    path(
        "widgets/<str:token>/conversation/",
        ChatWidgetConversationView.as_view(),
        name="widget_conversation",
    ),
    path(
        "widgets/<str:token>/agent-task/",
        ChatWidgetAgentTaskView.as_view(),
        name="widget_agent_task",
    ),
    path(
        "widgets/<str:token>/socket-auth/",
        ChatWidgetSocketAuthView.as_view(),
        name="widget_socket_auth",
    ),
    # Widget management endpoints (CRUD)
    path("widgets/", ChatWidgetView.as_view(), name="widget_list"),
    path("widgets/<int:id>/", ChatWidgetView.as_view(), name="widget_detail"),
    path("alerts", ConversationAlertView.as_view(), name="alert_list"),
    path("alerts/<uuid:id>/", ConversationAlertView.as_view(), name="alert_detail"),
    path("alerts/stats/", ConversationAlertStatsView.as_view(), name="alert_stats"),
    path("alert-rules/", ConversationAlertRuleView.as_view(), name="alert_rule_list"),
    path("alert-rules/<uuid:id>/", ConversationAlertRuleView.as_view(), name="alert_rule_detail"),
    path("tags/", TagView.as_view(), name="tag_list"),
    path("tags/<int:id>/", TagView.as_view(), name="tag_detail"),
]
