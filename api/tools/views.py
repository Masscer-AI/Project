from django.http import JsonResponse
from django.views import View
import uuid
import logging
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import TranscriptionJob
from django.contrib.auth.models import User
import os
from django.core.files import File

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class Transcriptions(View):
    def post(self, request):
        source = request.POST.get("source")
        user = User.objects.first()

        if source == "audio":
            audio_file = request.FILES.get("audio_file")
            if audio_file:
                transcription_job = TranscriptionJob.objects.create(
                    status="PENDING",
                    status_text="",
                    source_type="AUDIO",
                    user=user,
                    audio_file=audio_file,
                )
                return JsonResponse(
                    {"message": "Audio file received", "job_id": transcription_job.id}
                )

        elif source == "youtube_url":
            youtube_url = request.POST.get("youtube_url")
            if youtube_url:
                transcription_job = TranscriptionJob.objects.create(
                    status="PENDING",
                    status_text="",
                    source_type="YOUTUBE_URL",
                    user=user,
                    source_url=youtube_url,
                )
                logger.info(f"YouTube URL: {youtube_url}")
                return JsonResponse(
                    {"message": "YouTube URL received", "job_id": transcription_job.id}
                )

        elif source == "video":
            video_file = request.FILES.get("video_file")
            if video_file:
                unique_id = str(uuid.uuid4())
                video_ext = os.path.splitext(video_file.name)[1]
                video_filename = unique_id + video_ext

                django_file = File(video_file, name=video_filename)
                transcription_job = TranscriptionJob.objects.create(
                    status="PENDING",
                    status_text="",
                    source_type="VIDEO",
                    user=user,
                    video_file=django_file,
                )
                return JsonResponse(
                    {
                        "message": "Video file received",
                        "job_id": transcription_job.id,
                    }
                )

        return JsonResponse({"error": "Invalid data"}, status=400)
