from rest_framework import serializers
from .models import UserPreferences, WebPage


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


class WebPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebPage
        fields = [
            "id",
            "url",
            "title",
            "is_pinned",
            "created_at",
            "updated_at",
        ]
