from django.urls import path
from .views import (
    Transcriptions,
    VideoGenerationView,
    MediaView,
    ImageGenerationView,
    PromptNodeView,
    DocumentGeneratorView,
    DownloadFile,
    ImageEditorView,
)

app_name = "tools"

urlpatterns = [
    path("transcriptions/", Transcriptions.as_view(), name="transcriptions"),
    path("videos/", VideoGenerationView.as_view(), name="video_generation"),
    path("media/", MediaView.as_view(), name="get_media"),
    path("generate_image/", ImageGenerationView.as_view(), name="generate_image"),
    path("prompt_node/", PromptNodeView.as_view(), name="prompt_node"),
    path(
        "generate_document/", DocumentGeneratorView.as_view(), name="generate_document"
    ),
    path(
        "download/<path:file_path>/",
        DownloadFile.as_view(),
        name="download_file",
    ),
    path("image_editor/", ImageEditorView.as_view(), name="image_editor"),
]
