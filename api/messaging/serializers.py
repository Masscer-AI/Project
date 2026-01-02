from rest_framework import serializers
from .models import Message, Conversation, ChatWidget, ConversationAlert, ConversationAlertRule, Tag
from api.feedback.serializers import ReactionSerializer
from api.utils.timezone_utils import format_datetime_for_organization, get_organization_timezone_from_request


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

    class Meta:
        model = Conversation
        fields = "__all__"

    def get_number_of_messages(self, obj):
        return obj.messages.count()

    def get_summary(self, obj):
        """Get the AI-generated summary of the conversation."""
        return obj.summary or ""
    
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


class TagSerializer(serializers.ModelSerializer):
    organization = serializers.UUIDField(read_only=True, source="organization.id")
    
    class Meta:
        model = Tag
        fields = ['id', 'title', 'description', 'color', 'enabled', 'organization', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class BigConversationSerializer(serializers.ModelSerializer):
    messages = serializers.SerializerMethodField()  # Change to SerializerMethodField
    number_of_messages = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = "__all__"

    def get_messages(self, obj):
        # Retrieve messages ordered by ID
        ordered_messages = obj.messages.order_by('id')
        return MessageSerializer(ordered_messages, many=True, context=self.context).data  # Serialize the ordered messages with context

    def get_number_of_messages(self, obj):
        return obj.messages.count()  # This can stay the same



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
            "web_search_enabled",
            "rag_enabled",
            "plugins_enabled",
            "agent_slug",
            "agent_name",
        )


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