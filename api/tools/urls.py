from django.urls import path
from .views import (
    Transcriptions,
    VideoGenerationView,
    MediaView,
    ImageGenerationView,
    PromptNodeView,
)

app_name = "tools"

urlpatterns = [
    path("transcriptions/", Transcriptions.as_view(), name="transcriptions"),
    path("videos/", VideoGenerationView.as_view(), name="video_generation"),
    path("media/", MediaView.as_view(), name="get_media"),
    path("generate_image/", ImageGenerationView.as_view(), name="generate_image"),
    path("prompt_node/", PromptNodeView.as_view(), name="prompt_node"),
]
