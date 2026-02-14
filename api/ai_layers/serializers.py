# serializers.py
from rest_framework import serializers
from .models import Agent, LanguageModel, AgentSession


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


class AgentSessionSerializer(serializers.ModelSerializer):
    """Read-only serializer for AgentSession display (audit, debugging)."""

    agent_slug = serializers.SerializerMethodField()
    model_slug = serializers.SerializerMethodField()

    def _extract_slug(self, value):
        """Extract slug from string or from dict with id/slug/provider or id/slug/name."""
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, dict) and "slug" in value:
            return value["slug"]
        return None

    def get_agent_slug(self, obj):
        agent = obj.inputs.get("agent") if isinstance(obj.inputs, dict) else None
        return self._extract_slug(agent)

    def get_model_slug(self, obj):
        model = obj.inputs.get("model") if isinstance(obj.inputs, dict) else None
        return self._extract_slug(model)

    class Meta:
        model = AgentSession
        fields = [
            "id",
            "task_type",
            "iterations",
            "tool_calls_count",
            "total_duration",
            "agent_index",
            "agent_slug",
            "model_slug",
            "started_at",
            "ended_at",
        ]
        read_only_fields = fields

