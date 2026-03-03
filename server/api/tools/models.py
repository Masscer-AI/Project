from django.db import models
from django.contrib.auth.models import User
from moviepy.editor import concatenate_videoclips, VideoFileClip

import os
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile


class TranscriptionJob(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("DONE", "Done"),
        ("ERROR", "Error"),
    ]
    WHISPER_SIZE_CHOICES = [
        ("MEDIUM", "Medium"),
        ("TINY", "Tiny"),
        ("BASE", "Base"),
        ("SMALL", "Small"),
        ("LARGE_V3", "Large V3"),
    ]
    SOURCE_CHOICES = [
        ("YOUTUBE_URL", "YouTube URL"),
        ("AUDIO", "Audio"),
        ("VIDEO", "Video"),  # Added VIDEO as a source type
    ]
    name = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=7, choices=STATUS_CHOICES, default="PENDING")
    status_text = models.TextField()
    source_type = models.CharField(max_length=11, choices=SOURCE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    finished_at = models.DateTimeField(null=True, blank=True)
    source_url = models.URLField(blank=True, null=True)
    audio_file = models.FileField(
        upload_to="audio_files/", blank=True, null=True, max_length=255
    )
    whisper_size = models.CharField(
        max_length=15, choices=WHISPER_SIZE_CHOICES, default="SMALL"
    )
    video_file = models.FileField(
        upload_to="video_files/", blank=True, null=True, max_length=255
    )


class Transcription(models.Model):
    FORMAT_CHOICES = [
        ("VTT", "VTT"),
    ]

    transcription_job = models.ForeignKey(
        TranscriptionJob, on_delete=models.CASCADE, related_name="transcriptions"
    )
    format = models.CharField(max_length=3, choices=FORMAT_CHOICES, default="VTT")
    result = models.TextField()
    language = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)


class VideoGenerationJob(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("PROCESSING", "Processing"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
    ]
    DURATION_CHOICES = [
        ("LESS_THAN_MINUTE", "Less than a minute"),
        ("MORE_THAN_MINUTE", "More than a minute"),
    ]

    ORIENTATION_CHOICES = [
        ("LANDSCAPE", "Landscape"),
        ("PORTRAIT", "Portrait"),
        ("SQUARE", "Square"),
    ]

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING")
    status_text = models.TextField(null=True, blank=True)
    about = models.TextField()
    duration = models.CharField(
        max_length=20, choices=DURATION_CHOICES, default="LESS_THAN_MINUTE"
    )
    orientation = models.CharField(
        max_length=15, choices=ORIENTATION_CHOICES, default="LANDSCAPE"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    finished_at = models.DateTimeField(null=True, blank=True)


class Video(models.Model):
    video_generation_job = models.ForeignKey(
        VideoGenerationJob, on_delete=models.CASCADE, related_name="videos"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to="generated_videos/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def concatenate(self):
        # Fetch all chunks associated with this video
        chunks = VideoChunk.objects.filter(video=self)

        video_clips = []
        for chunk in chunks:
            if chunk.chunk_file:
                video_clips.append(VideoFileClip(chunk.chunk_file.path))

        if video_clips:
            # Concatenate video clips
            final_video = concatenate_videoclips(video_clips)

            # Define the path for the final video
            final_video_path = f"final_videos/concatenated_video_{self.pk}.mp4"

            # Save the final video to a temporary file
            temp_file_path = os.path.join(default_storage.location, final_video_path)
            final_video.write_videofile(temp_file_path, codec="libx264")

            # Save the final video file using Django's storage system
            with open(temp_file_path, "rb") as f:
                self.file.save(final_video_path, ContentFile(f.read()), save=True)

            # Close all video clips
            for clip in video_clips:
                clip.close()

            print(f"Final video saved at: {self.file.url}")
        else:
            print("No video chunks available to concatenate.")


class VideoChunk(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("PROCESSING", "Processing"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
    ]

    speech_text = models.TextField()  # String for speech text
    resource_query = models.TextField()  # String for resource query
    duration = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING")
    status_text = models.TextField(null=True, blank=True)
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name="chunks")
    chunk_file = models.FileField(upload_to="video_chunks/", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
