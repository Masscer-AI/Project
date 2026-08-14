from django.urls import path
from .views import (
    webhook,
    WSNumbersView,
    WSTemplatesView,
    WSConversationsView,
    WSConversationDetailView,
    WSNumberDetailView,
    WSNumberContactsView,
    WSContactDetailView,
)

app_name = "whatsapp"

urlpatterns = [
    path("webhook", webhook, name="webhook_handler"),
    path("numbers", WSNumbersView.as_view(), name="ws_numbers"),
    path("templates", WSTemplatesView.as_view(), name="ws_templates"),
    path(
        "numbers/<int:pk>/contacts",
        WSNumberContactsView.as_view(),
        name="ws_number_contacts",
    ),
    path("numbers/<str:number>", WSNumberDetailView.as_view(), name="ws_number_detail"),
    path(
        "contacts/<int:pk>",
        WSContactDetailView.as_view(),
        name="ws_contact_detail",
    ),
    path("conversations", WSConversationsView.as_view(), name="ws_conversations"),
    path(
        "conversations/<uuid:pk>",
        WSConversationDetailView.as_view(),
        name="ws_conversation_detail",
    ),
]
