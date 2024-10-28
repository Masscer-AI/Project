from .models import TrainingGenerator, Completion
from rest_framework import serializers


class TrainingGeneratorSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingGenerator
        fields = "__all__"


class CompletionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Completion
        fields = "__all__"
