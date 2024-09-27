from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
)
import traceback
from .models import Transcription, TranscriptionJob
from django.utils import timezone
import whisper
from moviepy.editor import VideoFileClip
import os

import threading
import time


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
            model = whisper.load_model("large")
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
            threading.Thread(target=delete_file_after_delay, args=(audio_path,)).start()  # Delete the audio file after processing
        elif job.source_type == "VIDEO":
            model = whisper.load_model("tiny")
            video_path = job.video_file.path
            audio_path = os.path.splitext(video_path)[0] + ".wav"  # Use the right extension from the video file name

            # Extract audio from video
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
            threading.Thread(target=delete_file_after_delay, args=(audio_path,)).start()  # Delete the extracted audio file after processing
            threading.Thread(target=delete_file_after_delay, args=(video_path,)).start()  # Delete the video file after processing

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
