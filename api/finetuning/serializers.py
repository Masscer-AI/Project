from .models import TrainingGenerator
from rest_framework import serializers


class TrainingGeneratorSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingGenerator
        fields = "__all__"
