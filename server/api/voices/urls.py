from django.urls import path

from .views import VoiceListView

app_name = "voices"

urlpatterns = [
    path("", VoiceListView.as_view(), name="voice_list"),
]
