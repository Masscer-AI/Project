from urllib.parse import urlparse

from rest_framework import serializers
from pydantic import ValidationError as PydanticValidationError
from .models import Message, Conversation, ChatWidget, ConversationAlert, ConversationAlertRule, Tag
from api.ai_layers.models import Agent
from api.feedback.serializers import ReactionSerializer
from api.utils.timezone_utils import format_datetime_for_organization, get_organization_timezone_from_request
from api.ai_layers.tools import list_available_tools
from .schemas import ChatWidgetStyle, ChatWidgetCapabilitiesPayload


class MessageSerializer(serializers.ModelSerializer):
    reactions = serializers.SerializerMethodField()
    created_at_formatted = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = "__all__"

    def get_reactions(self, obj):
        return ReactionSerializer(obj.reaction_set.all(), many=True).data
    
    def get_created_at_formatted(self, obj):
        """Retorna el created_at formateado según la zona horaria de la organización"""
        request = self.context.get('request')
        org_timezone = get_organization_timezone_from_request(request) if request else 'UTC'
        return format_datetime_for_organization(
            obj.created_at,
            org_timezone,
            '%Y-%m-%d %H:%M:%S %Z'
        )

    def validate(self, data):
        # Add custom validation logic here
        if data["type"] not in ["user", "assistant"]:
            raise serializers.ValidationError(
                "Invalid type. Must be 'user' or 'assistant'."
            )
        if not data["text"]:
            raise serializers.ValidationError("Text field cannot be empty.")
        return data


class ConversationSerializer(serializers.ModelSerializer):
    number_of_messages = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()
    created_at_formatted = serializers.SerializerMethodField()
    updated_at_formatted = serializers.SerializerMethodField()
    alerts_count = serializers.SerializerMethodField()
    alert_rule_ids = serializers.SerializerMethodField()
    has_pending_alerts = serializers.SerializerMethodField()
    is_anonymous_widget = serializers.SerializerMethodField()
    chat_widget_id = serializers.SerializerMethodField()
    visitor_alias = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = "__all__"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["user_id"] = instance.user_id if instance.user_id else None
        data["user_username"] = instance.user.username if instance.user else None
        return data

    def get_number_of_messages(self, obj):
        return obj.messages.count()

    def get_summary(self, obj):
        """Get the AI-generated summary of the conversation."""
        return obj.summary or ""

    def get_alerts_count(self, obj):
        return obj.alerts.count()

    def get_alert_rule_ids(self, obj):
        """Return distinct alert rule IDs triggered on this conversation."""
        return list(
            obj.alerts.values_list("alert_rule_id", flat=True).distinct()
        )

    def get_has_pending_alerts(self, obj):
        """True if any alert is PENDING or NOTIFIED (needs action)."""
        return obj.alerts.filter(status__in=["PENDING", "NOTIFIED"]).exists()
    
    def get_created_at_formatted(self, obj):
        """Retorna el created_at formateado según la zona horaria de la organización"""
        request = self.context.get('request')
        org_timezone = get_organization_timezone_from_request(request) if request else 'UTC'
        return format_datetime_for_organization(
            obj.created_at,
            org_timezone,
            '%Y-%m-%d %H:%M:%S %Z'
        )
    
    def get_updated_at_formatted(self, obj):
        """Retorna el updated_at formateado según la zona horaria de la organización"""
        request = self.context.get('request')
        org_timezone = get_organization_timezone_from_request(request) if request else 'UTC'
        return format_datetime_for_organization(
            obj.updated_at,
            org_timezone,
            '%Y-%m-%d %H:%M:%S %Z'
        )

    def get_is_anonymous_widget(self, obj):
        return obj.user_id is None and obj.chat_widget_id is not None

    def get_chat_widget_id(self, obj):
        return obj.chat_widget_id

    def get_visitor_alias(self, obj):
        session = getattr(obj, "widget_visitor_session", None)
        if not session:
            return None
        return f"visitor-{session.visitor_id[:8]}"


class TagSerializer(serializers.ModelSerializer):
    organization = serializers.UUIDField(read_only=True, source="organization.id")
    
    class Meta:
        model = Tag
        fields = ['id', 'title', 'description', 'color', 'enabled', 'organization', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class BigConversationSerializer(serializers.ModelSerializer):
    messages = serializers.SerializerMethodField()  # Change to SerializerMethodField
    number_of_messages = serializers.SerializerMethodField()
    is_anonymous_widget = serializers.SerializerMethodField()
    chat_widget_id = serializers.SerializerMethodField()
    visitor_alias = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = "__all__"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["user_id"] = instance.user_id if instance.user_id else None
        data["user_username"] = instance.user.username if instance.user else None
        return data

    def get_messages(self, obj):
        # Retrieve messages ordered by ID
        ordered_messages = obj.messages.order_by('id')
        return MessageSerializer(ordered_messages, many=True, context=self.context).data  # Serialize the ordered messages with context

    def get_number_of_messages(self, obj):
        return obj.messages.count()  # This can stay the same

    def get_is_anonymous_widget(self, obj):
        return obj.user_id is None and obj.chat_widget_id is not None

    def get_chat_widget_id(self, obj):
        return obj.chat_widget_id

    def get_visitor_alias(self, obj):
        session = getattr(obj, "widget_visitor_session", None)
        if not session:
            return None
        return f"visitor-{session.visitor_id[:8]}"



class WidgetConversationSummarySerializer(serializers.ModelSerializer):
    number_of_messages = serializers.SerializerMethodField()
    last_message_preview = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ["id", "created_at", "updated_at", "status", "number_of_messages", "last_message_preview"]

    def get_number_of_messages(self, obj):
        return obj.messages.count()

    def get_last_message_preview(self, obj):
        last_msg = obj.messages.order_by("-created_at").first()
        if not last_msg:
            return None
        return (last_msg.text or "")[:120]


class SharedConversationSerializer(serializers.ModelSerializer):
    conversation = BigConversationSerializer()

    class Meta:
        model = Conversation
        fields = "__all__"


class ChatWidgetConfigSerializer(serializers.ModelSerializer):
    agent_slug = serializers.SerializerMethodField()
    agent_name = serializers.SerializerMethodField()
    
    def get_agent_slug(self, obj):
        return obj.agent.slug if obj.agent else None
    
    def get_agent_name(self, obj):
        return obj.agent.name if obj.agent else None
    
    class Meta:
        model = ChatWidget
        fields = (
            "name",
            "enabled",
            "avatar_image",
            "style",
            "first_message",
            "capabilities",
            "agent_slug",
            "agent_name",
        )


class ChatWidgetSerializer(serializers.ModelSerializer):
    """Full serializer for CRUD operations on ChatWidget"""
    agent_slug = serializers.SerializerMethodField()
    agent_name = serializers.SerializerMethodField()
    agent_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    embed_code = serializers.SerializerMethodField()
    
    def get_agent_slug(self, obj):
        return obj.agent.slug if obj.agent else None
    
    def get_agent_name(self, obj):
        return obj.agent.name if obj.agent else None
    
    def get_embed_code(self, obj):
        from django.conf import settings

        # FRONTEND_URL first; if unset, use request host (from browser), else fallbacks
        base_url = getattr(settings, "FRONTEND_URL", "")
        if not base_url:
            request = self.context.get("request")
            if request:
                host = request.get_host()
                scheme = "https" if request.is_secure() else "http"
                base_url = f"{scheme}://{host}"
            else:
                base_url = getattr(
                    settings, "STREAMING_SERVER_URL", "http://localhost:8001"
                )
        base_url = base_url.rstrip("/")
        return f'<script src="{base_url}/widget/{obj.token}.js"></script>'

    def validate_style(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("style must be a JSON object.")

        try:
            parsed = ChatWidgetStyle.model_validate(value)
        except PydanticValidationError as exc:
            raise serializers.ValidationError(exc.errors()) from exc

        return parsed.model_dump(exclude_none=True)

    def validate_avatar_image(self, value):
        if value is None:
            return ""

        normalized = str(value).strip()
        if not normalized:
            return ""

        lowered = normalized.lower()
        if lowered.startswith("data:image/"):
            # Keep validation strict: only base64 encoded image data URLs.
            if ";base64," not in lowered:
                raise serializers.ValidationError(
                    "avatar_image data URL must be base64-encoded (missing ';base64,')."
                )
            return normalized

        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise serializers.ValidationError(
                "avatar_image must be an http(s) URL or a data:image/...;base64,... URL."
            )
        return normalized

    def validate_capabilities(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("capabilities must be a JSON array.")

        try:
            parsed_payload = ChatWidgetCapabilitiesPayload.model_validate(
                {"capabilities": value}
            )
        except PydanticValidationError as exc:
            raise serializers.ValidationError(exc.errors()) from exc

        available_tools = set(list_available_tools())
        invalid_names = sorted(
            cap.name for cap in parsed_payload.capabilities if cap.name not in available_tools
        )
        if invalid_names:
            raise serializers.ValidationError(
                f"Unknown capabilities: {', '.join(invalid_names)}"
            )

        return [cap.model_dump() for cap in parsed_payload.capabilities]
    
    class Meta:
        model = ChatWidget
        fields = (
            "id",
            "token",
            "name",
            "enabled",
            "avatar_image",
            "style",
            "first_message",
            "capabilities",
            "agent_slug",
            "agent_name",
            "agent_id",
            "embed_code",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "token", "created_at", "updated_at")
    
    def create(self, validated_data):
        agent_id = validated_data.pop('agent_id', None)
        if agent_id:
            from api.ai_layers.models import Agent
            validated_data['agent'] = Agent.objects.get(id=agent_id)
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        agent_id = validated_data.pop('agent_id', None)
        if agent_id is not None:
            from api.ai_layers.models import Agent
            validated_data['agent'] = Agent.objects.get(id=agent_id) if agent_id else None
        return super().update(instance, validated_data)


class ConversationAlertRuleSerializer(serializers.ModelSerializer):
    """
    Alert rules scope which chats raise an alert; delivery targets are NotificationRules, not notify_to here.
    """

    organization = serializers.UUIDField(read_only=True, source="organization.id")
    created_by = serializers.IntegerField(read_only=True, source="created_by.id", allow_null=True)
    agent_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        write_only=True,
    )

    class Meta:
        model = ConversationAlertRule
        fields = (
            "id",
            "name",
            "trigger",
            "extractions",
            "scope",
            "enabled",
            "agent_ids",
            "organization",
            "created_by",
            "created_at",
            "updated_at",
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["agent_ids"] = list(instance.agents.values_list("id", flat=True))
        return data

    def validate(self, attrs):
        scope = attrs.get("scope")
        if self.instance is not None and scope is None:
            scope = self.instance.scope
        has_agent_ids_key = "agent_ids" in attrs
        agent_ids = attrs.get("agent_ids")
        if scope == "selected_agents":
            if has_agent_ids_key:
                ids = agent_ids or []
            elif self.instance is not None:
                ids = list(self.instance.agents.values_list("id", flat=True))
            else:
                ids = []
            if not ids:
                raise serializers.ValidationError(
                    {
                        "agent_ids": "Select at least one agent when scope is limited to selected agents."
                    }
                )
        return attrs

    def _set_agents(self, instance, agent_ids):
        org = instance.organization
        if not agent_ids:
            instance.agents.clear()
            return
        allowed = set(Agent.objects.filter(organization=org).values_list("id", flat=True))
        bad = set(agent_ids) - allowed
        if bad:
            raise serializers.ValidationError(
                {"agent_ids": f"These agent ids are not in this organization: {sorted(bad)}"}
            )
        instance.agents.set(agent_ids)

    def create(self, validated_data):
        agent_ids = validated_data.pop("agent_ids", None)
        instance = super().create(validated_data)
        if agent_ids is not None:
            self._set_agents(instance, agent_ids)
        return instance

    def update(self, instance, validated_data):
        agent_ids = validated_data.pop("agent_ids", serializers.empty)
        instance = super().update(instance, validated_data)
        if agent_ids is not serializers.empty:
            self._set_agents(instance, agent_ids)
        return instance


class ConversationAlertSerializer(serializers.ModelSerializer):
    alert_rule = ConversationAlertRuleSerializer(read_only=True)
    conversation_title = serializers.SerializerMethodField()
    conversation_id = serializers.SerializerMethodField()
    resolved_by_username = serializers.SerializerMethodField()
    dismissed_by_username = serializers.SerializerMethodField()
    created_at_formatted = serializers.SerializerMethodField()
    updated_at_formatted = serializers.SerializerMethodField()

    class Meta:
        model = ConversationAlert
        fields = (
            "id",
            "title",
            "reasoning",
            "extractions",
            "status",
            "conversation",
            "conversation_title",
            "conversation_id",
            "alert_rule",
            "resolved_by",
            "resolved_by_username",
            "dismissed_by",
            "dismissed_by_username",
            "created_at",
            "created_at_formatted",
            "updated_at",
            "updated_at_formatted",
        )

    def get_conversation_title(self, obj):
        return obj.conversation.title or str(obj.conversation.id)

    def get_conversation_id(self, obj):
        return str(obj.conversation.id)

    def get_resolved_by_username(self, obj):
        return obj.resolved_by.username if obj.resolved_by else None

    def get_dismissed_by_username(self, obj):
        return obj.dismissed_by.username if obj.dismissed_by else None
    
    def get_created_at_formatted(self, obj):
        """Retorna el created_at formateado según la zona horaria de la organización"""
        request = self.context.get('request')
        org_timezone = get_organization_timezone_from_request(request) if request else 'UTC'
        return format_datetime_for_organization(
            obj.created_at,
            org_timezone,
            '%Y-%m-%d %H:%M:%S %Z'
        )
    
    def get_updated_at_formatted(self, obj):
        """Retorna el updated_at formateado según la zona horaria de la organización"""
        request = self.context.get('request')
        org_timezone = get_organization_timezone_from_request(request) if request else 'UTC'
        return format_datetime_for_organization(
            obj.updated_at,
            org_timezone,
            '%Y-%m-%d %H:%M:%S %Z'
        )