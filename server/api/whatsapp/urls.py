from django.urls import path
from .views import (
    webhook,
    WSNumbersView,
    WSConversationsView,
    WSConversationDetailView,
    WSNumberDetailView,
)

app_name = "whatsapp"

urlpatterns = [
    path("webhook", webhook, name="webhook_handler"),
    path("numbers", WSNumbersView.as_view(), name="ws_numbers"),
    path("numbers/<str:number>", WSNumberDetailView.as_view(), name="ws_number_detail"),
    path("conversations", WSConversationsView.as_view(), name="ws_conversations"),
    path(
        "conversations/<int:pk>",
        WSConversationDetailView.as_view(),
        name="ws_conversation_detail",
    ),
]
