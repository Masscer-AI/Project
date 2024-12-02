from rest_framework import serializers
from .models import UserPreferences


class UserPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreferences
        fields = [
            "id",
            "max_memory_messages",
            "autoscroll",
            "autoplay",
            "background_image_source",
            "background_image_opacity",
            "theme",
            "multiagentic_modality",
        ]
