# serializers.py
from rest_framework import serializers
from .models import Agent

class AgentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Agent
        fields = ['id', 'name', 'slug', 'model_slug', 'system_prompt', 'salute', 'act_as', 'user', 'is_public']
