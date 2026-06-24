from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from api.notify.alert_dispatch import (
    _delivery_includes_app,
    emit_in_app_notification_created,
)
from api.notify.models import UserNotification


class InAppNotificationPushTests(SimpleTestCase):
    def test_delivery_includes_app(self):
        self.assertTrue(_delivery_includes_app(UserNotification.DELIVERY_APP))
        self.assertTrue(_delivery_includes_app(UserNotification.DELIVERY_ALL))
        self.assertFalse(_delivery_includes_app(UserNotification.DELIVERY_EMAIL))

    @patch("api.notify.actions.notify_user")
    @patch("api.notify.serializers.UserNotificationSerializer")
    def test_emit_skips_email_only(self, serializer_cls, notify_user):
        notification = MagicMock()
        notification.delivery_method = UserNotification.DELIVERY_EMAIL
        emit_in_app_notification_created(notification)
        notify_user.assert_not_called()
        serializer_cls.assert_not_called()

    @patch("api.notify.actions.notify_user")
    @patch("api.notify.serializers.UserNotificationSerializer")
    def test_emit_pushes_app_delivery(self, serializer_cls, notify_user):
        notification = MagicMock()
        notification.delivery_method = UserNotification.DELIVERY_APP
        notification.target_user_id = 42
        serializer_cls.return_value.data = {"id": "abc", "message": "Hello"}

        emit_in_app_notification_created(notification)

        notify_user.assert_called_once_with(
            42,
            "in_app_notification_created",
            {"id": "abc", "message": "Hello"},
        )
