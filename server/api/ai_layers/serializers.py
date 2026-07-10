import json

from rest_framework import serializers

from api.voices.access import voice_is_accessible
from api.voices.models import Voice

from .models import Agent, LanguageModel, AgentSession


def _extract_slug(value):
    """Extract slug from string or nested ref dict."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and "slug" in value:
        return value["slug"]
    return None


def _extract_agent_name(agent_value) -> str | None:
    if isinstance(agent_value, dict):
        name = agent_value.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return None


def _parse_maybe_json(value):
    """Parse JSON strings when possible; otherwise return the original value."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value
    return value


def _preview_value(value, limit=280):
    if value is None:
        return ""
    if isinstance(value, str):
        preview = value
    else:
        preview = json.dumps(value, default=str, ensure_ascii=False)
    return preview if len(preview) <= limit else f"{preview[:limit - 3]}..."


def extract_tool_calls_from_messages(messages):
    """
    Reconstruct ordered tool calls from AgentLoop messages.

    Stored history may contain OpenAI response items (``function_call`` /
    ``function_call_output``) or the same keys emitted by
    :class:`api.ai_layers.vertex_gemini_agent_loop.VertexGeminiAgentLoop` for
    UI compatibility.
    """
    if not isinstance(messages, list):
        return []

    tool_calls = []
    call_index = {}
    current_iteration = 0
    in_function_batch = False

    for message in messages:
        if not isinstance(message, dict):
            in_function_batch = False
            continue

        item_type = message.get("type")

        if item_type == "function_call":
            if not in_function_batch:
                current_iteration += 1
                in_function_batch = True

            call_id = message.get("call_id") or message.get("id") or f"call_{len(tool_calls) + 1}"
            tool_call = {
                "order": len(tool_calls) + 1,
                "iteration": current_iteration or None,
                "call_id": call_id,
                "tool_name": message.get("name") or "unknown",
                "arguments": _parse_maybe_json(message.get("arguments", {})),
                "result": None,
                "result_preview": "",
                "error": None,
            }
            tool_calls.append(tool_call)
            call_index[call_id] = tool_call
            continue

        in_function_batch = False

        if item_type != "function_call_output":
            continue

        call_id = message.get("call_id") or f"call_output_{len(tool_calls) + 1}"
        output = _parse_maybe_json(message.get("output"))

        tool_call = call_index.get(call_id)
        if tool_call is None:
            tool_call = {
                "order": len(tool_calls) + 1,
                "iteration": None,
                "call_id": call_id,
                "tool_name": "unknown",
                "arguments": {},
                "result": None,
                "result_preview": "",
                "error": None,
            }
            tool_calls.append(tool_call)
            call_index[call_id] = tool_call

        tool_call["result"] = output
        tool_call["result_preview"] = _preview_value(output)

        if isinstance(output, dict):
            error_value = output.get("error")
            if error_value:
                tool_call["error"] = (
                    error_value if isinstance(error_value, str) else _preview_value(error_value)
                )

    return tool_calls


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
    default_voice_id = serializers.PrimaryKeyRelatedField(
        queryset=Voice.objects.filter(is_active=True),
        source="default_voice",
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Agent
        fields = [
            "id",
            "name",
            "slug",
            "agent_kind",
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
            "default_voice_id",
            "profile_picture_url",
            "max_tokens",
            "llm",
            "conversation_title_prompt",
        ]
        read_only_fields = ["agent_kind"]

    def validate_default_voice_id(self, voice):
        if voice is None:
            return voice
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        organization = None
        if user is not None and user.is_authenticated:
            from api.messaging.tasks import get_user_organization

            organization = get_user_organization(user)
        if user is not None and not voice_is_accessible(
            voice, user=user, organization=organization
        ):
            raise serializers.ValidationError("Voice is not accessible to this user.")
        return voice
    
    def get_organization(self, obj):
        """Return organization ID if it exists, None otherwise"""
        return str(obj.organization.id) if obj.organization else None

    def get_access_mode(self, obj):
        """
        - personal: no organization
        - org_all: organization agent with no role restrictions
        - org_roles: organization agent restricted to specific roles
        - platform: platform assistant (feature-flag gated)
        """
        from api.ai_layers.models import AgentKind

        if obj.agent_kind == AgentKind.PLATFORM_ASSISTANT:
            return "platform"
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
        return _extract_slug(value)

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


class AgentSessionExecutionLogSerializer(serializers.ModelSerializer):
    session_id = serializers.UUIDField(source="id", read_only=True)
    agent_slug = serializers.SerializerMethodField()
    agent_name = serializers.SerializerMethodField()
    model_slug = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    tool_calls = serializers.SerializerMethodField()
    event_log = serializers.SerializerMethodField()

    class Meta:
        model = AgentSession
        fields = [
            "session_id",
            "agent_index",
            "agent_slug",
            "agent_name",
            "model_slug",
            "iterations",
            "tool_calls_count",
            "total_duration",
            "started_at",
            "ended_at",
            "status",
            "tool_calls",
            "event_log",
        ]
        read_only_fields = fields

    def get_agent_slug(self, obj):
        agent = obj.inputs.get("agent") if isinstance(obj.inputs, dict) else None
        return _extract_slug(agent)

    def get_agent_name(self, obj):
        agent = obj.inputs.get("agent") if isinstance(obj.inputs, dict) else None
        return _extract_agent_name(agent)

    def get_model_slug(self, obj):
        model = obj.inputs.get("model") if isinstance(obj.inputs, dict) else None
        return _extract_slug(model)

    def get_status(self, obj):
        if isinstance(obj.outputs, dict):
            return obj.outputs.get("status", "completed")
        return "completed"

    def get_tool_calls(self, obj):
        messages = obj.outputs.get("messages", []) if isinstance(obj.outputs, dict) else []
        return extract_tool_calls_from_messages(messages)

    def get_event_log(self, obj):
        log = getattr(obj, "event_log", None)
        return log if isinstance(log, list) else []

