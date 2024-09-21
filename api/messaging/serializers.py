from rest_framework import serializers
from .models import Message, Conversation

class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = '__all__'

    def validate(self, data):
        # Add custom validation logic here
        if data['type'] not in ['user', 'assistant']:
            raise serializers.ValidationError("Invalid type. Must be 'user' or 'assistant'.")
        if not data['text']:
            raise serializers.ValidationError("Text field cannot be empty.")
        return data

class ConversationSerializer(serializers.ModelSerializer):
    number_of_messages = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = '__all__'

    def get_number_of_messages(self, obj):
        return obj.messages.count()

class BigConversationSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    number_of_messages = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = '__all__'

    def get_number_of_messages(self, obj):
        return obj.messages.count()
