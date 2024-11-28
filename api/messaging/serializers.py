from rest_framework import serializers
from .models import Message, Conversation
from api.feedback.serializers import ReactionSerializer


class MessageSerializer(serializers.ModelSerializer):
    reactions = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = "__all__"

    def get_reactions(self, obj):
        return ReactionSerializer(obj.reaction_set.all(), many=True).data

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

    class Meta:
        model = Conversation
        fields = "__all__"

    def get_number_of_messages(self, obj):
        return obj.messages.count()



class BigConversationSerializer(serializers.ModelSerializer):
    messages = serializers.SerializerMethodField()  # Change to SerializerMethodField
    number_of_messages = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = "__all__"

    def get_messages(self, obj):
        # Retrieve messages ordered by ID
        ordered_messages = obj.messages.order_by('id')
        return MessageSerializer(ordered_messages, many=True).data  # Serialize the ordered messages

    def get_number_of_messages(self, obj):
        return obj.messages.count()  # This can stay the same



class SharedConversationSerializer(serializers.ModelSerializer):
    conversation = BigConversationSerializer()

    class Meta:
        model = Conversation
        fields = "__all__"
