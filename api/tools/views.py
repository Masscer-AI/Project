from django.http import JsonResponse
from django.views import View
import uuid
import json
import logging
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import TranscriptionJob, VideoGenerationJob
from .serializers import TranscriptionJobSerializer
import os
from django.core.files import File
from api.authenticate.decorators.token_required import token_required

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class Transcriptions(View):

    def get(self, request):
        user = request.user
        transcription_jobs = TranscriptionJob.objects.filter(user=user)
        serializer = TranscriptionJobSerializer(transcription_jobs, many=True)
        return JsonResponse(serializer.data, safe=False)

    def post(self, request):
        source = request.POST.get("source")
        whisper_size = request.POST.get("whisper_size")
        whisper_size = whisper_size.upper()
        print("WHISPER SIZE REQUESTED,", whisper_size)
        user = request.user

        if source == "audio":
            audio_file = request.FILES.get("audio_file")
            if audio_file:
                transcription_job = TranscriptionJob.objects.create(
                    name=audio_file.name,
                    status="PENDING",
                    status_text="",
                    source_type="AUDIO",
                    user=user,
                    audio_file=audio_file,
                    whisper_size=whisper_size,
                )
                return JsonResponse(
                    {"message": "Audio file received", "job_id": transcription_job.id}
                )

        elif source == "youtube_url":
            youtube_url = request.POST.get("youtube_url")
            if youtube_url:
                transcription_job = TranscriptionJob.objects.create(
                    name=youtube_url,
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
                    name=video_file.name,
                    status="PENDING",
                    status_text="",
                    source_type="VIDEO",
                    user=user,
                    video_file=django_file,
                    whisper_size=whisper_size,
                )
                return JsonResponse(
                    {
                        "message": "Video file received",
                        "job_id": transcription_job.id,
                    }
                )

        return JsonResponse({"error": "Invalid data"}, status=400)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class VideoGenerationView(View):

    def post(self, request):
        user = request.user

        data = json.loads(request.body)
        about = data.get("about")

        duration = data.get("duration", "LESS_THAN_MINUTE").upper()
        orientation = data.get("orientation", "LANDSCAPE").upper()

        video_generation_job = VideoGenerationJob.objects.create(
            status="PENDING",
            status_text="",
            about=about,
            duration=duration,
            orientation=orientation,
            user=user,
        )

        return JsonResponse(
            {
                "message": "Video generation job created",
                "job_id": video_generation_job.id,
            }
        )
