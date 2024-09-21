from django.urls import path
from .views import ConversationView, MessageView

app_name = "messaging"

urlpatterns = [
    path('conversations', ConversationView.as_view(), name='conversation_list'),
    path('conversations/<uuid:id>/', ConversationView.as_view(), name='conversation_detail'),
    path('messages', MessageView.as_view(), name='message_list'),
    path('messages/<int:id>/', MessageView.as_view(), name='message_detail'),
]
