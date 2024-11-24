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
            "theme",
        ]
