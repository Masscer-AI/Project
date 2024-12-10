import requests
import uuid
from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip
from django.conf import settings

from pydantic import BaseModel, Field
from typing import List
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
)

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
from api.utils.document_tools import convert_html
import threading
import time

SAVE_PATH = os.path.join(settings.MEDIA_ROOT, "generated")


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
            video_clip.close()  # Close the video clip to release the file

            # Transcribe the extracted audio
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
