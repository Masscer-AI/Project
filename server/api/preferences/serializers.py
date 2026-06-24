from pydantic import ValidationError as PydanticValidationError
from rest_framework import serializers

from .models import UserPreferences, WebPage
from .notification_settings import (
    default_notification_settings_dict,
    normalize_notification_settings,
)


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
            "notification_settings",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["notification_settings"] = normalize_notification_settings(
            instance.notification_settings
        )
        return data

    def validate_notification_settings(self, value):
        if value is None:
            return default_notification_settings_dict()
        try:
            return normalize_notification_settings(value)
        except PydanticValidationError as exc:
            raise serializers.ValidationError(exc.errors()) from exc


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
