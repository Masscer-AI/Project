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
    access_mode = serializers.SerializerMethodField()
    allowed_roles = serializers.SerializerMethodField()

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
            "access_mode",
            "allowed_roles",
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

    def get_access_mode(self, obj):
        """
        - personal: no organization
        - org_all: organization agent with no role restrictions
        - org_roles: organization agent restricted to specific roles
        """
        if not obj.organization_id:
            return "personal"
        # If there are any through rows, the agent is role-restricted.
        has_restrictions = getattr(obj, "role_access_assignments", None) and obj.role_access_assignments.exists()
        return "org_roles" if has_restrictions else "org_all"

    def get_allowed_roles(self, obj):
        if not obj.organization_id:
            return []
        roles = obj.allowed_roles.all().only("id", "name")
        return [{"id": str(r.id), "name": r.name} for r in roles]


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

