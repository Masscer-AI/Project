from django.urls import path
from .views import Transcriptions, VideoGenerationView

app_name = "tools"

urlpatterns = [
    path('transcriptions/', Transcriptions.as_view(), name='transcriptions'),
    path('videos/', VideoGenerationView.as_view(), name='video_generation'),
]