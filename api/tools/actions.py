import requests
import uuid
from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip
from django.conf import settings
from django.contrib.auth.models import User

from pydantic import BaseModel, Field
from typing import List
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
)

from api.authenticate.models import CredentialsManager, Organization

import traceback
from .models import (
    Transcription,
    TranscriptionJob,
    VideoGenerationJob,
    Video,
    VideoChunk,
)
from django.utils import timezone
import whisper

import os
from api.utils.openai_functions import create_structured_completion, generate_speech_api
from api.utils.runway_functions import image_to_video
from api.utils.document_tools import convert_html
from api.messaging.models import Message
import threading
import time
from api.notify.actions import notify_user
from api.generations.models import VideoGeneration, AudioGeneration
from api.utils.color_printer import printer
from api.utils.elevenlabs_functions import generate_audio_elevenlabs

SAVE_PATH = os.path.join(settings.MEDIA_ROOT, "generated")

os.makedirs(SAVE_PATH, exist_ok=True)


def format_time_vtt(time):
    minutes = int(time // 60)
    seconds = int(time % 60)
    milliseconds = int((time % 1) * 1000)
    return f"{minutes:02}:{seconds:02}.{milliseconds:03}"


def get_available_transcriptions(video_url):
    try:
        # Verificar si la URL es válida
        if "youtube.com/watch?v=" not in video_url:
            raise ValueError(
                "La URL del vídeo no es válida. Asegúrate de que esté en el formato correcto."
            )

        # Extraer el ID del video de la URL
        video_id = video_url.split("v=")[1]

        # Obtener las transcripciones disponibles
        transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
        available_transcriptions = {}

        for transcript in transcripts:
            language_code = transcript.language_code
            transcript_data = transcript.fetch()
            vtt_transcript = "WEBVTT\n\n"
            for entry in transcript_data:
                start_time = format_time_vtt(entry["start"])
                end_time = format_time_vtt(entry["start"] + entry["duration"])
                vtt_transcript += f"{start_time} --> {end_time}\n{entry['text']}\n\n"
            available_transcriptions[language_code] = vtt_transcript

        return available_transcriptions

    except (TranscriptsDisabled, NoTranscriptFound) as e:
        print(f"No se encontraron transcripciones para el video: {e}")
        return {}
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return {}


def delete_file_after_delay(file_path, delay=5):
    """Delete a file after a specified delay."""
    time.sleep(delay)
    try:
        os.remove(file_path)
        print(f"File {file_path} deleted successfully.")
    except Exception as e:
        print(f"Error deleting file {file_path}: {e}")


def transcribe(job_id):
    try:
        job = TranscriptionJob.objects.get(id=job_id)
        print(
            f"Initializing transcription job. Source type: {job.source_type}. Whisper size: {job.whisper_size}"
        )

        if job.source_type == "YOUTUBE_URL":
            transcriptions = get_available_transcriptions(job.source_url)
            for language_code, vtt_transcript in transcriptions.items():
                Transcription.objects.create(
                    transcription_job=job,
                    format="VTT",
                    result=vtt_transcript,
                    language=language_code,
                )
            job.status = "DONE"
        elif job.source_type == "AUDIO":
            model = whisper.load_model(job.whisper_size.lower())
            audio_path = job.audio_file.path

            if not os.path.exists(audio_path):
                printer.red("The audio file does not exist!")
                raise Exception("The audio file for transcription does not exist!")

            audio_path = os.path.normpath(job.audio_file.path)
            result = model.transcribe(audio_path)
            vtt_transcript = "WEBVTT\n\n"
            for segment in result["segments"]:
                start_time = format_time_vtt(segment["start"])
                end_time = format_time_vtt(segment["end"])
                vtt_transcript += f"{start_time} --> {end_time}\n{segment['text']}\n\n"
            Transcription.objects.create(
                transcription_job=job,
                format="VTT",
                result=vtt_transcript,
                language=result["language"],
            )
            job.status = "DONE"
            threading.Thread(target=delete_file_after_delay, args=(audio_path,)).start()
        elif job.source_type == "VIDEO":
            model = whisper.load_model(job.whisper_size.lower())
            video_path = job.video_file.path
            audio_path = os.path.splitext(video_path)[0] + ".wav"
            video_clip = VideoFileClip(video_path)
            video_clip.audio.write_audiofile(audio_path)
            video_clip.close()

            result = model.transcribe(audio_path)
            vtt_transcript = "WEBVTT\n\n"
            for segment in result["segments"]:
                start_time = format_time_vtt(segment["start"])
                end_time = format_time_vtt(segment["end"])
                vtt_transcript += f"{start_time} --> {end_time}\n{segment['text']}\n\n"
            Transcription.objects.create(
                transcription_job=job,
                format="VTT",
                result=vtt_transcript,
                language=result["language"],
            )
            job.status = "DONE"
            threading.Thread(target=delete_file_after_delay, args=(audio_path,)).start()
            threading.Thread(target=delete_file_after_delay, args=(video_path,)).start()

        job.finished_at = timezone.now()
        job.save()
        return {"message": "Transcription completed successfully", "job_id": job.id}

    except TranscriptionJob.DoesNotExist:
        return {"error": "Transcription job not found", "job_id": job_id}
    except Exception as e:
        job.status = "ERROR"
        job.status_text = str(e)
        job.finished_at = timezone.now()
        job.save()
        return {"error": str(e), "job_id": job.id}


def fetch_images(query, per_page=15, page=1, orientation="landscape"):
    url = f"https://api.pexels.com/v1/search?query={query}&per_page={per_page}&page={page}&orientation={orientation}"
    headers = {"Authorization": os.getenv("PEXELS_API_KEY")}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        return {"error": response.status_code, "message": response.text}


def fetch_videos(query, per_page=15, page=1, orientation="landscape"):
    url = f"https://api.pexels.com/videos/search?query={query}&per_page={per_page}&page={page}&orientation={orientation}"
    headers = {"Authorization": os.getenv("PEXELS_API_KEY")}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        return {"error": response.status_code, "message": response.text}


class Portion(BaseModel):
    speech: str = Field(..., description="The text to be spoken")
    resources_query: str = Field(
        ...,
        description="A 3-5 words query to use to retrieve media from Pexels API and add to this portion of the script",
    )


class Script(BaseModel):
    title: str = Field(..., description="The title of the video to generate")
    portions: List[Portion] = Field(
        ..., description="A list of portions for the final video."
    )


def generate_video(video_job_id: int):
    video_job = VideoGenerationJob.objects.get(pk=video_job_id)
    _system = f"""You are a powerful video scripting assistant. You task is to generate a narrative video script in portions. You must provide also a video title at the beginning. Then each portion will be an small part of the video. Keep in mind that the expected duration of the video is {video_job.duration}. 
    
    Each portion contains a `speech` property that as its name indicated, will be the spoken audio for this portion of the video.

    The `resources_query` is a text to search media files in the Pexels API and use as background for the video.
    """

    script = create_structured_completion(
        system_prompt=_system,
        response_format=Script,
        user_prompt=f"Make a video about: `{video_job.about}`",
    )
    video = Video.objects.create(title=script.title, video_generation_job=video_job)

    spoken = ""
    for p in script.portions:
        spoken += p.speech

        VideoChunk.objects.create(
            speech_text=p.speech,
            resource_query=p.resources_query,
            video=video,
            status="PENDING",
        )


def generate_chunk_video(video_chunk_id: int):
    chunk = VideoChunk.objects.get(pk=video_chunk_id)

    # Update status to PROCESSING
    chunk.status = "PROCESSING"
    chunk.save()

    audio_output_path = os.path.join(
        settings.MEDIA_ROOT,
        f"audio_chunks/video_{chunk.video.pk}_chunk_{video_chunk_id}.mp3",
    )
    audio_duration = None

    os.makedirs(os.path.join(settings.MEDIA_ROOT, "video_chunks"), exist_ok=True)
    os.makedirs(os.path.join(settings.MEDIA_ROOT, "final_videos"), exist_ok=True)

    try:
        generate_speech_api(text=chunk.speech_text, output_path=audio_output_path)

        audio_file_clip = AudioFileClip(audio_output_path)
        audio_duration = audio_file_clip.duration

        # Fetch videos from Pexels using the resources_query
        pexels_videos = fetch_videos(query=chunk.resource_query, per_page=5)

        video_clips = []
        total_duration = 0

        # Download videos and keep track of their durations
        for video in pexels_videos.get("videos", []):
            video_url = video["video_files"][0]["link"]
            video_response = requests.get(video_url)

            # Save the video locally
            video_path = os.path.join(
                settings.MEDIA_ROOT,
                f"video_chunks/video_{chunk.video.pk}_chunk_{video_chunk_id}.mp4",
            )
            with open(video_path, "wb") as f:
                f.write(video_response.content)

            # Load the video clip
            clip = VideoFileClip(video_path)
            video_clips.append(clip)
            total_duration += clip.duration

            # Stop if we have enough duration
            if total_duration >= audio_duration:
                break

        # Concatenate video clips
        final_video = concatenate_videoclips(video_clips)

        # Trim the final video to match the audio duration
        final_video = final_video.subclip(0, audio_duration)

        # Set the audio to the final video
        final_video = final_video.set_audio(AudioFileClip(audio_output_path))

        # Save the final video
        final_video_path = os.path.join(
            settings.MEDIA_ROOT,
            f"final_videos/video_{chunk.video.pk}_chunk_{video_chunk_id}.mp4",
        )
        final_video.write_videofile(final_video_path, codec="libx264")

        # Update status to COMPLETED
        chunk.status = "COMPLETED"
        chunk.chunk_file = final_video_path
        chunk.save()

        if not VideoChunk.objects.filter(
            video=chunk.video, status__in=["PROCESSING", "PENDING"]
        ).exists():
            chunk.video.concatenate()

    except Exception as e:
        # Update status to FAILED in case of an error
        chunk.status = "FAILED"
        chunk.status_text = str(e)  # Save the error message
        chunk.save()
        print(f"Error processing video chunk: {e}")

    finally:
        for clip in video_clips:
            clip.close()

        # # Remove the audio file after use
        # if os.path.exists(audio_output_path):
        #     os.remove(audio_output_path)


# This should return the path to the generated file
def create_html_file_from_string(html_string, output_file):
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_string)

    return output_file


def document_convertion(source_text: str, from_type="html", to_type="docx"):

    input_file_path = f"{uuid.uuid4()}.{from_type}"
    output_file_path = f"{SAVE_PATH}/{uuid.uuid4()}.{to_type}"
    create_html_file_from_string(source_text, input_file_path)
    convert_html(input_file_path, output_file_path, to_type)

    return input_file_path, output_file_path


def append_attachment_to_message(message_id, attachment_type, extra_data={}):
    m = Message.objects.get(pk=message_id)
    m.attachments.append(
        {
            "type": attachment_type,
            **extra_data,
        }
    )
    m.save()


def generate_video_from_image(
    prompt_image_b64, prompt_text, ratio, user_id, provider="runway", message_id=None
):
    try:
        if provider == "runway":
            user = User.objects.get(pk=user_id)
            task = image_to_video(prompt_image_b64, prompt_text, ratio)
            result_url = task.output[0]

            video_path = f"generations/videos/{uuid.uuid4()}.mp4"
            os.makedirs(
                os.path.join(settings.MEDIA_ROOT, "generations/videos"), exist_ok=True
            )

            with open(os.path.join(settings.MEDIA_ROOT, video_path), "wb") as f:
                f.write(requests.get(result_url).content)

            video_generation = VideoGeneration.objects.create(
                name=f"Video generated from image {message_id}",
                prompt=prompt_text,
                message_id=message_id,
                user=user,
                ratio=ratio,
                engine="runway",
                file=video_path,
            )
            m = Message.objects.get(pk=message_id)
            m.attachments.append(
                {
                    "type": "video_generation",
                    "id": str(video_generation.id),
                    "content": f"{settings.MEDIA_URL}{video_path}",
                    "name": f"Video generated from image {message_id}",
                    "text": prompt_text,
                }
            )
            m.save()

            notify_user(
                user_id,
                event_type="video_generated",
                data={
                    "message_id": message_id,
                    "public_url": f"{settings.MEDIA_URL}{video_path}",
                },
            )

            return True
        else:
            raise Exception(f"The provider {provider} is not supported yet!")
    except Exception as e:
        printer.red(e)
        return None


def generate_audio(text, voice, provider, user_id, message_id):

    # Ensure audio directory exists
    audio_store_path = "generations/audios"
    os.makedirs(os.path.join(settings.MEDIA_ROOT, audio_store_path), exist_ok=True)

    try:
        # Get the user organizations
        user = User.objects.get(pk=user_id)
        organizations = Organization.objects.filter(owner=user)
        credentials = CredentialsManager.objects.filter(organization__in=organizations)

        # Get the API_KEY of the first one with eleven_labs_api_key
        eleven_labs_api_key = None
        for credential in credentials:
            if credential.elevenlabs_api_key:
                eleven_labs_api_key = credential.elevenlabs_api_key
                break

        if provider == "elevenlabs":
            audio_path = f"generations/audios/{uuid.uuid4()}.mp3"
            save_path = os.path.join(settings.MEDIA_ROOT, audio_path)
            generate_audio_elevenlabs(
                text,
                voice,
                eleven_labs_api_key,
                save_path,
            )

            audio_generation = AudioGeneration.objects.create(
                text=text,
                voice=voice,
                provider=provider,
                user=user,
                file=audio_path,
            )

            append_attachment_to_message(
                message_id,
                "audio_generation",
                {
                    "id": str(audio_generation.id),
                    "content": f"{settings.MEDIA_URL}{audio_path}",
                },
            )

            notify_user(
                user_id,
                event_type="audio_generated",
                data={
                    "message_id": message_id,
                },
            )
            return True
        else:

            raise Exception(f"The provider {provider} is not supported yet!")

    except Exception as e:

        printer.red(e)
        return None
