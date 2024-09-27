from django.contrib import admin
from .models import TranscriptionJob, Transcription
from .tasks import async_transcribe


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
