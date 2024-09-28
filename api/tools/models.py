from django.db import models
from django.contrib.auth.models import User

class TranscriptionJob(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('DONE', 'Done'),
        ('ERROR', 'Error'),
    ]
    
    SOURCE_CHOICES = [
        ('YOUTUBE_URL', 'YouTube URL'),
        ('AUDIO', 'Audio'),
        ('VIDEO', 'Video'),  # Added VIDEO as a source type
    ]
    name = models.CharField(max_length=255, null=True, blank=True) 
    status = models.CharField(max_length=7, choices=STATUS_CHOICES, default='PENDING')
    status_text = models.TextField()
    source_type = models.CharField(max_length=11, choices=SOURCE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    finished_at = models.DateTimeField(null=True, blank=True)
    source_url = models.URLField(blank=True, null=True)  
    audio_file = models.FileField(upload_to='audio_files/', blank=True, null=True, max_length=255)
    video_file = models.FileField(upload_to='video_files/', blank=True, null=True, max_length=255) 

class Transcription(models.Model):
    FORMAT_CHOICES = [
        ('VTT', 'VTT'),
    ]
    
    transcription_job = models.ForeignKey(TranscriptionJob, on_delete=models.CASCADE, related_name='transcriptions')
    format = models.CharField(max_length=3, choices=FORMAT_CHOICES, default='VTT')
    result = models.TextField()
    language = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)
