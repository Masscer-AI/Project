from rest_framework import serializers
from .models import Reaction, ReactionTemplate

class ReactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reaction
        fields = "__all__"


class ReactionTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReactionTemplate
        fields = "__all__"

