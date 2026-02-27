from rest_framework import serializers
from pydantic import ValidationError as PydanticValidationError
from .models import Message, Conversation, ChatWidget, ConversationAlert, ConversationAlertRule, Tag
from api.feedback.serializers import ReactionSerializer
from api.utils.timezone_utils import format_datetime_for_organization, get_organization_timezone_from_request
from .schemas import ChatWidgetStyle


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
            "style",
            "web_search_enabled",
            "rag_enabled",
            "plugins_enabled",
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
        import os
        from django.conf import settings
        
        # Get streaming server URL from environment or settings
        streaming_url = os.getenv(
            "STREAMING_SERVER_URL", 
            getattr(settings, "STREAMING_SERVER_URL", None)
        )
        
        # If not configured, build from request
        if not streaming_url:
            request = self.context.get('request')
            if request:
                host = request.get_host()
                scheme = 'https' if request.is_secure() else 'http'
                streaming_url = f"{scheme}://{host}"
            else:
                streaming_url = "https://your-streaming-server.com"
        
        # Remove trailing slash if present
        streaming_url = streaming_url.rstrip('/')
        
        return f'<script src="{streaming_url}/widget/{obj.token}.js"></script>'

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
    
    class Meta:
        model = ChatWidget
        fields = (
            "id",
            "token",
            "name",
            "enabled",
            "style",
            "web_search_enabled",
            "rag_enabled",
            "plugins_enabled",
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
    organization = serializers.UUIDField(read_only=True, source="organization.id")
    created_by = serializers.IntegerField(read_only=True, source="created_by.id", allow_null=True)
    
    class Meta:
        model = ConversationAlertRule
        fields = (
            "id",
            "name",
            "trigger",
            "extractions",
            "scope",
            "enabled",
            "notify_to",
            "organization",
            "created_by",
            "created_at",
            "updated_at",
        )


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