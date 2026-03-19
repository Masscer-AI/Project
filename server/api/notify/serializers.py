from rest_framework import serializers
from api.notify.models import NotificationRule, UserNotification
from api.notify.schemas import NotificationConditionList


class NotificationRuleSerializer(serializers.ModelSerializer):
    organization = serializers.UUIDField(read_only=True, source="organization.id")
    created_by = serializers.IntegerField(
        read_only=True, source="created_by.id", allow_null=True
    )

    # Read-only resolved labels for display
    notify_to_user_username = serializers.SerializerMethodField()
    notify_to_role_name = serializers.SerializerMethodField()
    notify_to_org_name = serializers.SerializerMethodField()
    alert_rule_name = serializers.SerializerMethodField()

    # Write-only IDs accepted from the client
    notify_to_user_id = serializers.IntegerField(
        write_only=True, required=False, allow_null=True
    )
    notify_to_role_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )
    notify_to_org_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )
    alert_rule_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = NotificationRule
        fields = (
            "id",
            "organization",
            "alert_rule_id",
            "alert_rule_name",
            "notify_to_user_id",
            "notify_to_user_username",
            "notify_to_role_id",
            "notify_to_role_name",
            "notify_to_org_id",
            "notify_to_org_name",
            "conditions",
            "enabled",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "organization", "created_by", "created_at", "updated_at")

    def get_notify_to_user_username(self, obj):
        return obj.notify_to_user.username if obj.notify_to_user_id else None

    def get_notify_to_role_name(self, obj):
        return obj.notify_to_role.name if obj.notify_to_role_id else None

    def get_notify_to_org_name(self, obj):
        return obj.notify_to_org.name if obj.notify_to_org_id else None

    def get_alert_rule_name(self, obj):
        return obj.alert_rule.name if obj.alert_rule_id else None

    def validate_conditions(self, value):
        try:
            NotificationConditionList(conditions=value)
        except Exception as exc:
            raise serializers.ValidationError(str(exc))
        return value

    def validate(self, data):
        user_id = data.get("notify_to_user_id")
        role_id = data.get("notify_to_role_id")
        org_id = data.get("notify_to_org_id")

        # On update, check existing values too
        if self.instance:
            if "notify_to_user_id" not in data:
                user_id = self.instance.notify_to_user_id
            if "notify_to_role_id" not in data:
                role_id = self.instance.notify_to_role_id
            if "notify_to_org_id" not in data:
                org_id = self.instance.notify_to_org_id

        set_targets = [t for t in [user_id, role_id, org_id] if t is not None]
        if len(set_targets) != 1:
            raise serializers.ValidationError(
                "Exactly one of notify_to_user_id, notify_to_role_id, or notify_to_org_id must be provided."
            )
        return data

    def _resolve_relations(self, validated_data):
        from django.contrib.auth.models import User
        from api.authenticate.models import Role, Organization
        from api.messaging.models import ConversationAlertRule

        if "alert_rule_id" in validated_data:
            validated_data["alert_rule"] = ConversationAlertRule.objects.get(
                id=validated_data.pop("alert_rule_id")
            )
        if "notify_to_user_id" in validated_data:
            uid = validated_data.pop("notify_to_user_id")
            validated_data["notify_to_user"] = User.objects.get(id=uid) if uid else None
        if "notify_to_role_id" in validated_data:
            rid = validated_data.pop("notify_to_role_id")
            validated_data["notify_to_role"] = Role.objects.get(id=rid) if rid else None
        if "notify_to_org_id" in validated_data:
            oid = validated_data.pop("notify_to_org_id")
            validated_data["notify_to_org"] = Organization.objects.get(id=oid) if oid else None

        return validated_data

    def create(self, validated_data):
        return super().create(self._resolve_relations(validated_data))

    def update(self, instance, validated_data):
        return super().update(instance, self._resolve_relations(validated_data))
