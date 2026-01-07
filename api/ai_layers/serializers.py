# serializers.py
from rest_framework import serializers
from .models import Agent, LanguageModel


class LanguageModelSerializer(serializers.ModelSerializer):
    provider = serializers.StringRelatedField()

    class Meta:
        model = LanguageModel
        fields = ["id", "provider", "slug", "name", "pricing"]


class AgentSerializer(serializers.ModelSerializer):
    llm = LanguageModelSerializer(read_only=True)
    organization = serializers.SerializerMethodField()

    class Meta:
        model = Agent
        fields = [
            "id",
            "name",
            "slug",
            "system_prompt",
            "salute",
            "act_as",
            "user",
            "organization",
            "is_public",
            "model_provider",
            "default",
            "presence_penalty",
            "frequency_penalty",
            "top_p",
            "openai_voice",
            "profile_picture_url",
            "max_tokens",
            "temperature",
            "llm",
            "conversation_title_prompt",
        ]
    
    def get_organization(self, obj):
        """Return organization ID if it exists, None otherwise"""
        return str(obj.organization.id) if obj.organization else None


