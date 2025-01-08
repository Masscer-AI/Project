from django.http import JsonResponse
from django.utils.text import slugify
import base64
import json
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import requests
from django.conf import settings

import uuid
import logging
from .models import TranscriptionJob, VideoGenerationJob, Video
from .serializers import TranscriptionJobSerializer, VideoSerializer
import os
from django.core.files import File
from api.authenticate.decorators.token_required import token_required
from .actions import fetch_videos, document_convertion
from api.utils.openai_functions import generate_image
from api.messaging.models import Message
from api.utils.color_printer import printer
from api.utils.openai_functions import create_completion_openai
from django.http import HttpResponse
from api.utils.black_forest_labs import (
    request_flux_generation,
    get_result_url,
    request_image_edit_with_mask,
    generate_with_control_image,
)

from .tasks import async_image_to_video


SAVE_PATH = os.path.join(settings.MEDIA_ROOT, "generated")
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
class ImageToVideo(View):
    def get(self, request):
        user = request.user

        videos = Video.objects.filter(video_generation_job__user=user)

        serializer = VideoSerializer(videos, many=True)

        return JsonResponse(serializer.data, safe=False)

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


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class MediaView(View):

    def get(self, request):
        query = request.GET.get("query", "")
        per_page = request.GET.get("per_page", 15)
        page = request.GET.get("page", 1)
        orientation = request.GET.get("orientation", "landscape")

        try:
            # Convert per_page and page to integers
            per_page = int(per_page)
            page = int(page)

            # Fetch videos from Pexels
            response_data = fetch_videos(query, per_page, page, orientation)

            if "error" in response_data:
                return JsonResponse(response_data, status=400)

            return JsonResponse(response_data, safe=False)

        except ValueError:
            return JsonResponse(
                {"error": "Invalid integer values for per_page or page"}, status=400
            )


def get_width_and_height_from_size_string(size: str):
    printer.red(f"SIZE: {size}")
    # SPlit at x
    split_size = size.split("x")
    width = int(split_size[0])
    height = int(split_size[1])
    return width, height


LIST_OF_FLUX_MODELS = [
    "flux-pro-1.1-ultra",
    "flux-pro-1.1",
    "flux-pro",
    "flux-dev",
]


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class ImageGenerationView(View):
    def post(self, request):
        try:
            data = json.loads(request.body)
            prompt = data.get("prompt")
            message_id = data.get("message_id")
            size = data.get("size")
            model = data.get("model")

            if model in LIST_OF_FLUX_MODELS:
                width, height = get_width_and_height_from_size_string(size)
                request_id = request_flux_generation(
                    prompt=prompt, width=width, height=height, model=model, steps=40
                )
                if not request_id:
                    raise Exception("Failed to generate image")
                image_url = get_result_url(request_id)
            else:
                image_url = generate_image(prompt=prompt, model=model, size=size)

            image_response = requests.get(image_url)
            image_content = image_response.content

            image_content_b64 = base64.b64encode(image_content).decode("utf-8")
            image_content_b64 = f"data:image/png;base64,{image_content_b64}"
            image_name = slugify(prompt[:100])
            if message_id:
                m = Message.objects.get(id=message_id)
                attachments = m.attachments or []
                attachments.append(
                    {
                        "type": "image",
                        "content": image_content_b64,
                        "name": image_name,
                    }
                )
                m.attachments = attachments
                m.save()
            return JsonResponse(
                {
                    "image_url": image_url,
                    "image_content_b64": image_content_b64,
                    "image_name": image_name,
                }
            )

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class PromptNodeView(View):
    def post(self, request):
        data = json.loads(request.body)

        system_prompt = data.get("system_prompt")
        model = data.get("model")
        user_message = data.get("user_message")

        printer.red(f"SYSTEM PROMPT: {system_prompt}")
        printer.red(f"USER MESSAGE: {user_message}")
        printer.red(f"MODEL: {model}")
        response = create_completion_openai(
            system_prompt=system_prompt, user_message=user_message, model=model
        )
        return JsonResponse({"response": response})


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class DocumentGeneratorView(View):
    def post(self, request):
        data = json.loads(request.body)
        source_text = data.get("source_text")
        from_type = data.get("from_type")
        to_type = data.get("to_type")
        input_document_created_path, output_filepath = document_convertion(
            source_text, from_type, to_type
        )

        os.remove(input_document_created_path)
        # Return only the last section of the path, not the full path
        file_name = os.path.basename(output_filepath)

        return JsonResponse({"output_filepath": file_name})


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class DownloadFile(View):
    def get(self, request, file_path):
        file_name = os.path.normpath(file_path)

        # COncatenate the file path with the save path
        full_path = os.path.join(SAVE_PATH, file_name)

        if not os.path.exists(full_path):
            return JsonResponse({"error": "File not found"}, status=404)

        with open(full_path, "rb") as file:
            response = HttpResponse(
                file.read(), content_type="application/octet-stream"
            )
            response["Content-Disposition"] = (
                f'attachment; filename="{os.path.basename(full_path)}"'
            )

        # delete the file after download
        os.remove(full_path)
        return response


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class ImageEditorView(View):
    def post(self, request):
        try:
            data = json.loads(request.body)
            image_base64 = data.get("image")
            prompt = data.get("prompt")
            mask_base64 = data.get("mask")
            steps = data.get("steps", 50)
            prompt_upsampling = data.get("prompt_upsampling", False)
            guidance = data.get("guidance", 60)
            output_format = data.get("output_format", "png")
            safety_tolerance = data.get("safety_tolerance", 4)

            # Call the request_image_edit_with_mask function
            request_id = request_image_edit_with_mask(
                image_base64=image_base64,
                prompt=prompt,
                mask_base64=mask_base64,
                steps=steps,
                prompt_upsampling=prompt_upsampling,
                guidance=guidance,
                output_format=output_format,
                safety_tolerance=safety_tolerance,
                api_key=os.environ.get("BFL_API_KEY"),
            )

            if not request_id:
                raise Exception("Failed to edit image")

            # Get the result URL after the request
            image_url = get_result_url(request_id)

            # Get the image content and convert it to Base64
            image_response = requests.get(image_url)
            image_content = image_response.content
            image_content_b64 = base64.b64encode(image_content).decode("utf-8")
            image_content_b64 = f"data:image/jpeg;base64,{image_content_b64}"

            image_name = slugify(prompt[:100])

            return JsonResponse(
                {
                    "image_url": image_url,
                    "image_content_b64": image_content_b64,
                    "image_name": image_name,
                }
            )

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)


class ImageVaryView(View):
    def post(self, request):
        data = json.loads(request.body)
        prompt = data.get("prompt")
        control_image_base64 = data.get("control_image_base64")
        # model = data.get("model", "flux-dev")
        # steps = data.get("steps", 50)
        # prompt_upsampling = data.get("prompt_upsampling", False)
        guidance = data.get("guidance", 30)
        # output_format = data.get("output_format", "jpeg")
        safety_tolerance = data.get("safety_tolerance", 2)

        request_id = generate_with_control_image(
            prompt=prompt,
            control_image_base64=control_image_base64,
            # model=model,
            # steps=steps,
            # prompt_upsampling=prompt_upsampling,
            guidance=guidance,
            # output_format=output_format,
            safety_tolerance=safety_tolerance,
        )

        if not request_id:
            raise Exception("Failed to generate image")

        image_url = get_result_url(request_id)

        image_response = requests.get(image_url)
        image_content = image_response.content
        image_content_b64 = base64.b64encode(image_content).decode("utf-8")
        image_content_b64 = f"data:image/jpeg;base64,{image_content_b64}"

        image_name = slugify(prompt[:100])

        return JsonResponse(
            {
                "image_url": image_url,
                "image_content_b64": image_content_b64,
                "image_name": image_name,
            }
        )


def fetch_url_content(url: str):
    try:
        res = requests.get(url)
        res.raise_for_status()  # Raise an error for bad responses

        # Check the Content-Type to determine how to handle the response
        content_type = res.headers.get("Content-Type", "")
        if "application/json" in content_type:
            content = res.json()  # Parse JSON response
        else:
            content = res.text  # Fallback to text response

        return content, res.status_code, res.headers, content_type
    except requests.RequestException as e:
        # Handle any request errors as appropriate
        return str(e), 500, {}, ""


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class WebsiteFetcherView(View):
    def post(self, request):
        data = json.loads(request.body)
        url = data.get("url")

        content, status_code, headers, content_type = fetch_url_content(url)

        # Convert headers to a normal dict
        headers_dict = dict(headers)

        return JsonResponse(
            {
                "content": content,
                "status_code": status_code,
                "headers": headers_dict,
                "content_type": content_type,
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class ImageToVideoView(View):
    def post(self, request):
        data = json.loads(request.body)
        prompt_image_b64 = data.get("image_b64")
        prompt_text = data.get("prompt")
        ratio = data.get("ratio")
        message_id = data.get("message_id")

        async_image_to_video.delay(
            prompt_image_b64,
            prompt_text,
            ratio=ratio,
            user_id=request.user.id,
            message_id=message_id,
        )

        return JsonResponse(
            {
                "message": "Video generation job created, you'll receive a notification when ready"
            }
        )
