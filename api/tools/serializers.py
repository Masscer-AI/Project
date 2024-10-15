from rest_framework import serializers
from .models import TranscriptionJob, Transcription, Video, VideoGenerationJob, VideoChunk

class TranscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transcription
        fields = '__all__'

class TranscriptionJobSerializer(serializers.ModelSerializer):
    transcriptions = TranscriptionSerializer(many=True, read_only=True)

    class Meta:
        model = TranscriptionJob
        fields = '__all__'


class VideoChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoChunk
        fields = '__all__'

class VideoGenerationJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoGenerationJob
        fields = '__all__'

class VideoSerializer(serializers.ModelSerializer):
    chunks = VideoChunkSerializer(many=True, read_only=True)

    class Meta:
        model = Video
        fields = '__all__'