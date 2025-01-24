from django.urls import path
from .views import (
    Transcriptions,
    ImageToVideo,
    MediaView,
    ImageGenerationView,
    PromptNodeView,
    DocumentGeneratorView,
    DownloadFile,
    ImageEditorView,
    WebsiteFetcherView,
    ImageToVideoView,
)

app_name = "tools"

urlpatterns = [
    path("transcriptions/", Transcriptions.as_view(), name="transcriptions"),
    path(
        "transcriptions/<int:job_id>/",
        Transcriptions.as_view(),
        name="transcription_detail",
    ),
    path("videos/", ImageToVideo.as_view(), name="video_generation"),
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
    path("website_fetcher/", WebsiteFetcherView.as_view(), name="website_fetcher"),
    path(
        "video_generator/image_to_video/",
        ImageToVideoView.as_view(),
        name="video_generator",
    ),
]
