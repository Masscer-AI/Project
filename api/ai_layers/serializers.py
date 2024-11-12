# serializers.py
from rest_framework import serializers
from .models import Agent, LanguageModel


class LanguageModelSerializer(serializers.ModelSerializer):
    provider = serializers.StringRelatedField()

    class Meta:
        model = LanguageModel
        fields = ["id", "provider", "slug", "name", "created_at", "updated_at"]


class AgentSerializer(serializers.ModelSerializer):
    llm = LanguageModelSerializer(read_only=True) 

    class Meta:
        model = Agent
        fields = [
            "id",
            "name",
            "slug",
            "model_slug",
            "system_prompt",
            "salute",
            "act_as",
            "user",
            "is_public",
            "model_provider",
            "default",
            "presence_penalty",
            "frequency_penalty",
            "top_p",
            "profile_picture_url",
            "max_tokens",
            "temperature",
            "llm", 
        ]
