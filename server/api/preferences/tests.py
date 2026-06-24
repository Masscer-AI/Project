from django.contrib.auth.models import User
from django.test import TestCase
from pydantic import ValidationError

from api.preferences.notification_settings import (
    NotificationSettings,
    default_notification_settings_dict,
    normalize_notification_settings,
)
from api.preferences.serializers import UserPreferencesSerializer


class NotificationSettingsSchemaTests(TestCase):
    def test_defaults(self):
        data = default_notification_settings_dict()
        self.assertTrue(data["activated"])
        self.assertEqual(data["volume"], 0.12)
        self.assertEqual(data["success_tone_ref"], "chime_success_ascending")
        self.assertEqual(data["failure_tone_ref"], "chime_error_descending")

    def test_normalize_fills_missing_keys(self):
        merged = normalize_notification_settings({"volume": 0.5})
        self.assertEqual(merged["volume"], 0.5)
        self.assertTrue(merged["activated"])

    def test_volume_bounds(self):
        with self.assertRaises(ValidationError):
            NotificationSettings.model_validate({"volume": 1.5})

    def test_rejects_unknown_keys(self):
        with self.assertRaises(ValidationError):
            NotificationSettings.model_validate({"activated": True, "foo": "bar"})

    def test_invalid_tone_ref(self):
        with self.assertRaises(ValidationError):
            NotificationSettings.model_validate(
                {"success_tone_ref": "nonexistent_tone"}
            )


class UserPreferencesSerializerNotificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="prefsuser", password="test")

    def test_serializer_includes_normalized_notification_settings(self):
        from api.preferences.models import UserPreferences

        prefs = UserPreferences.objects.create(user=self.user, notification_settings={})
        data = UserPreferencesSerializer(prefs).data
        self.assertEqual(
            data["notification_settings"],
            default_notification_settings_dict(),
        )

    def test_validate_notification_settings_rejects_bad_volume(self):
        serializer = UserPreferencesSerializer(
            data={"notification_settings": {"volume": 2.0}}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("notification_settings", serializer.errors)
