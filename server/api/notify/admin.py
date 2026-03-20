from django.contrib import admin

from api.notify.models import Notification, NotificationRule, UserNotification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "message_preview", "read_at", "created_at")
    list_filter = ("created_at",)
    search_fields = ("message", "user__username", "user__email")
    raw_id_fields = ("user",)
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"

    @admin.display(description="Message")
    def message_preview(self, obj):
        text = (obj.message or "")[:80]
        return f"{text}…" if len(obj.message or "") > 80 else text


@admin.register(NotificationRule)
class NotificationRuleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "organization",
        "alert_rule",
        "notify_target",
        "enabled",
        "created_at",
    )
    list_filter = ("enabled", "organization", "alert_rule", "created_at")
    search_fields = (
        "id",
        "organization__name",
        "alert_rule__name",
        "notify_to_user__username",
        "notify_to_user__email",
    )
    raw_id_fields = (
        "organization",
        "alert_rule",
        "notify_to_user",
        "notify_to_role",
        "notify_to_org",
        "created_by",
    )
    readonly_fields = ("id", "created_at", "updated_at")
    date_hierarchy = "created_at"

    @admin.display(description="Notify target")
    def notify_target(self, obj):
        return obj._target_label()


@admin.register(UserNotification)
class UserNotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "target_user",
        "organization",
        "notification_rule",
        "alert",
        "delivery_method",
        "read_at",
        "created_at",
    )
    list_filter = ("delivery_method", "organization", "created_at")
    search_fields = (
        "id",
        "message",
        "target_user__username",
        "target_user__email",
        "organization__name",
    )
    raw_id_fields = (
        "organization",
        "notification_rule",
        "alert",
        "target_user",
    )
    readonly_fields = ("id", "created_at")
    date_hierarchy = "created_at"
