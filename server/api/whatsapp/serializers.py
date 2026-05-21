from rest_framework import serializers

from api.ai_layers.serializers import AgentSerializer

from .models import WSNumber


class WSNumberSerializer(serializers.ModelSerializer):
    conversations_count = serializers.SerializerMethodField()
    agent = AgentSerializer(read_only=True)

    def get_conversations_count(self, obj):
        return obj.conversations.count()

    class Meta:
        model = WSNumber
        fields = "__all__"
