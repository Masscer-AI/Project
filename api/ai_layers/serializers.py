# serializers.py
from rest_framework import serializers
from .models import Agent,LanguageModel

class AgentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Agent
        fields = ['id', 'name', 'slug', 'model_slug', 'system_prompt', 'salute', 'act_as', 'user', 'is_public', 'model_provider']


class LanguageModelSerializer(serializers.ModelSerializer):
    provider = serializers.StringRelatedField()
    class Meta:
        model = LanguageModel
        fields = ['id', 'provider', 'slug', 'name', 'created_at', 'updated_at']