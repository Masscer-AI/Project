from django.contrib import admin
from .models import (
    TranscriptionJob,
    Transcription,
    VideoGenerationJob,
    Video,
    VideoChunk,
)
from .tasks import async_transcribe
from .actions import generate_video, generate_chunk_video


@admin.register(TranscriptionJob)
class TranscriptionJobAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "source_type", "created_at", "user", "finished_at")
    actions = ["transcribe_action"]

    def transcribe_action(self, request, queryset):
        for job in queryset:
            if job.status == "DONE":
                self.message_user(request, f"Transcription job {job.id} already DONE")
                return
            async_transcribe.delay(job.id)
            self.message_user(request, "Transcription task initialized")

    transcribe_action.short_description = "Transcribe selected jobs"


@admin.register(Transcription)
class TranscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "transcription_job", "format", "language", "created_at")


# Registering VideoGenerationJob and Video models
@admin.register(VideoGenerationJob)
class VideoGenerationJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "duration",
        "orientation",
        "created_at",
        "user",
        "finished_at",
    )
    actions = ["generate"]

    def generate(self, request, queryset):
        for v in queryset:
            generate_video(v.id)

    


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ("id", "video_generation_job", "title", "created_at")

    actions = ["concatenate"]
    def concatenate(self, request, queryset):
        for v in queryset:
            v.concatenate()


@admin.register(VideoChunk)
class VideoChunkAdmin(admin.ModelAdmin):
    list_display = ("id", "status","created_at")
    actions = ["generate"]

    def generate(self, request, queryset):
        for v in queryset:
            generate_chunk_video(v.id)
