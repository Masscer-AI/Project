from rest_framework import serializers

from api.ai_layers.serializers import AgentSerializer

from .models import WSContact, WSNumber


class WSNumberSerializer(serializers.ModelSerializer):
    conversations_count = serializers.SerializerMethodField()
    agent = AgentSerializer(read_only=True)
    access_user_id = serializers.IntegerField(allow_null=True, read_only=True)
    allowed_roles = serializers.SerializerMethodField()

    def get_conversations_count(self, obj):
        return obj.conversations.count()

    def get_allowed_roles(self, obj):
        roles = obj.allowed_roles.all().only("id", "name")
        return [{"id": str(r.id), "name": r.name} for r in roles]

    class Meta:
        model = WSNumber
        fields = [
            "id",
            "organization",
            "user",
            "agent",
            "name",
            "capabilities",
            "number",
            "platform_id",
            "waba_id",
            "access_mode",
            "access_user_id",
            "allowed_roles",
            "verified",
            "certicate_b64",
            "created_at",
            "updated_at",
            "conversations_count",
        ]


class WSContactSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True, allow_null=True)
    user_email = serializers.SerializerMethodField()
    user_display_name = serializers.SerializerMethodField()
    last_activity_at = serializers.SerializerMethodField()

    class Meta:
        model = WSContact
        fields = [
            "id",
            "ws_number",
            "number",
            "display_name",
            "user_id",
            "user_email",
            "user_display_name",
            "last_activity_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_user_email(self, obj) -> str | None:
        if not obj.user_id:
            return None
        return obj.user.email or None

    def get_user_display_name(self, obj) -> str | None:
        if not obj.user_id:
            return None
        profile = getattr(obj.user, "profile", None)
        if profile and (profile.name or "").strip():
            return profile.name.strip()
        return obj.user.username or obj.user.email or None

    def get_last_activity_at(self, obj):
        conv = (
            obj.conversations.order_by("-last_message_at", "-updated_at")
            .values_list("last_message_at", "updated_at")
            .first()
        )
        if not conv:
            return None
        last_message_at, updated_at = conv
        return last_message_at or updated_at
