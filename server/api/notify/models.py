import uuid
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from api.authenticate.models import Organization, Role
from api.messaging.models import ConversationAlertRule, ConversationAlert
from api.notify.schemas import NotificationConditionList


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()

    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class NotificationRule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="notification_rules",
    )
    alert_rule = models.ForeignKey(
        ConversationAlertRule,
        on_delete=models.CASCADE,
        related_name="notification_rules",
    )

    # Exactly one of these three must be set — enforced in clean()
    notify_to_user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="notification_rules",
    )
    notify_to_role = models.ForeignKey(
        Role,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="notification_rules",
    )
    notify_to_org = models.ForeignKey(
        Organization,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="notification_rules_as_target",
    )

    # List of NotificationCondition objects — validated via NotificationConditionList schema
    conditions = models.JSONField(
        default=list,
        help_text=(
            "List of condition objects. Each must match the NotificationCondition schema. "
            "Example: [{\"subject\": \"n_alerts\", \"condition\": \"n_alerts > 5\", "
            "\"delivery_method\": \"app\", \"message\": \"{{n_alerts}} pending alerts!\"}]"
        ),
    )

    enabled = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_notification_rules",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        targets = [self.notify_to_user, self.notify_to_role, self.notify_to_org]
        set_targets = [t for t in targets if t is not None]
        if len(set_targets) != 1:
            raise ValidationError(
                "Exactly one of notify_to_user, notify_to_role, or notify_to_org must be set."
            )

        # Validate conditions schema
        try:
            NotificationConditionList(conditions=self.conditions)
        except Exception as exc:
            raise ValidationError({"conditions": str(exc)}) from exc

    def __str__(self):
        return f"NotificationRule({self.alert_rule_id}) → {self._target_label()}"

    def _target_label(self):
        if self.notify_to_user_id:
            return f"user:{self.notify_to_user_id}"
        if self.notify_to_role_id:
            return f"role:{self.notify_to_role_id}"
        if self.notify_to_org_id:
            return f"org:{self.notify_to_org_id}"
        return "unset"


class UserNotification(models.Model):
    DELIVERY_APP = "app"
    DELIVERY_EMAIL = "email"
    DELIVERY_ALL = "all"
    DELIVERY_CHOICES = [
        (DELIVERY_APP, "App"),
        (DELIVERY_EMAIL, "Email"),
        (DELIVERY_ALL, "All"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="user_notifications",
    )
    notification_rule = models.ForeignKey(
        NotificationRule,
        on_delete=models.CASCADE,
        related_name="user_notifications",
    )
    alert = models.ForeignKey(
        ConversationAlert,
        on_delete=models.CASCADE,
        related_name="user_notifications",
    )
    target_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="user_notifications",
    )

    delivery_method = models.CharField(
        max_length=10,
        choices=DELIVERY_CHOICES,
        default=DELIVERY_APP,
    )
    message = models.TextField()

    # Lifecycle timestamps
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the notification was actually sent/delivered to the user.",
    )
    read_at = models.DateTimeField(null=True, blank=True)
    ignored_at = models.DateTimeField(null=True, blank=True)

    # Set to now+30d when read_at or ignored_at is set — cleanup task will use this
    expires_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"UserNotification({self.target_user_id}, rule={self.notification_rule_id})"
