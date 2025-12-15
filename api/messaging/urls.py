from django.urls import path
from .views import (
    ConversationView,
    MessageView,
    upload_audio,
    get_suggestion,
    SharedConversationView,
    ChatWidgetConfigView,
    ChatWidgetAuthTokenView,
    ConversationAlertView,
    ConversationAlertStatsView,
    ConversationAlertRuleView,
)

app_name = "messaging"

urlpatterns = [
    path("conversations", ConversationView.as_view(), name="conversation_list"),
    path(
        "conversations/<uuid:id>/",
        ConversationView.as_view(),
        name="conversation_detail",
    ),
    path("messages", MessageView.as_view(), name="message_list"),
    path("messages/<int:id>/", MessageView.as_view(), name="message_detail"),
    path("upload-audio/", upload_audio, name="upload_audio"),
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
        "widgets/<str:token>/auth-token/",
        ChatWidgetAuthTokenView.as_view(),
        name="widget_auth_token",
    ),
    path("alerts", ConversationAlertView.as_view(), name="alert_list"),
    path("alerts/<uuid:id>/", ConversationAlertView.as_view(), name="alert_detail"),
    path("alerts/stats/", ConversationAlertStatsView.as_view(), name="alert_stats"),
    path("alert-rules/", ConversationAlertRuleView.as_view(), name="alert_rule_list"),
    path("alert-rules/<uuid:id>/", ConversationAlertRuleView.as_view(), name="alert_rule_detail"),
]
