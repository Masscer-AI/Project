from django.urls import path

from .views import VoiceListView, VoicePreviewView

app_name = "voices"

urlpatterns = [
    path("", VoiceListView.as_view(), name="voice_list"),
    path("preview/", VoicePreviewView.as_view(), name="voice_preview"),
]
