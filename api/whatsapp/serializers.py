from .models import WSNumber, WSConversation, WSMessage, WSContact
from rest_framework import serializers
from api.ai_layers.serializers import AgentSerializer


class WSNumberSerializer(serializers.ModelSerializer):
    # It must return the number of conversations and messages

    conversations_count = serializers.SerializerMethodField()
    # messages_count = serializers.SerializerMethodField()

    agent = AgentSerializer(read_only=True)

    def get_conversations_count(self, obj):
        return obj.wsconversation_set.count()

    class Meta:
        model = WSNumber
        fields = "__all__"


class WSMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = WSMessage
        fields = "__all__"


class WSConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = WSConversation
        fields = "__all__"


class BigWSConversationSerializer(serializers.ModelSerializer):
    messages = WSMessageSerializer(many=True)

    class Meta:
        model = WSConversation
        fields = "__all__"


class WSContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = WSContact
        fields = "__all__"
