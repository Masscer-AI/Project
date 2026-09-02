from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from pydantic import ValidationError as PydanticValidationError
from .models import (
    Organization,
    CredentialsManager,
    UserProfile,
    FeatureFlag,
    FeatureFlagAssignment,
    Role,
    RoleAssignment,
    OrganizationInvite,
)
from .phone_numbers import (
    default_phone_numbers_list,
    normalize_phone_numbers,
    validate_phone_numbers_for_storage,
)
from rest_framework.exceptions import ValidationError
from django.db import transaction

class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    email = serializers.EmailField(required=True)
    organization_id = serializers.UUIDField(required=False, write_only=True)
    organization_name = serializers.CharField(required=False, write_only=True, max_length=255)

    class Meta:
        model = User
        fields = ["email", "password", "organization_id", "organization_name"]

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise ValidationError("A user with this email already exists.")
        return value

    def validate_organization_id(self, value):
        try:
            self._organization = Organization.objects.get(id=value)
        except Organization.DoesNotExist as err:
            raise ValidationError("Organization does not exist.") from err
        return value

    def validate(self, attrs):
        has_org_id = "organization_id" in attrs and attrs["organization_id"]
        has_org_name = "organization_name" in attrs and attrs["organization_name"]

        if not has_org_id and not has_org_name:
            raise ValidationError(
                "Either organization_id or organization_name must be provided."
            )
        if has_org_id and has_org_name:
            raise ValidationError(
                "Provide either organization_id or organization_name, not both."
            )
        return attrs

    def create(self, validated_data):
        organization_id = validated_data.pop("organization_id", None)
        organization_name = validated_data.pop("organization_name", None)

        email = validated_data["email"]
        base_username = email.split("@")[0]
        username = base_username
        suffix = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{suffix}"
            suffix += 1

        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                email=email,
                password=validated_data["password"],
            )

            if organization_name:
                organization = Organization.objects.create(
                    name=organization_name,
                    owner=user,
                )
                try:
                    from api.assignments.actions import ensure_owner_onboarding

                    ensure_owner_onboarding(user, organization)
                except Exception:
                    pass
            else:
                organization = getattr(self, "_organization", None)
                if organization is None:
                    organization = Organization.objects.select_for_update().get(
                        id=organization_id
                    )

            user_profile, _ = UserProfile.objects.get_or_create(user=user)
            user_profile.organization = organization
            user_profile.save(update_fields=["organization", "updated_at"])

            return user

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise ValidationError("Passwords do not match.")

        validate_password(attrs["new_password"])
        return attrs

class OrganizationInviteCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    name = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")
    bio = serializers.CharField(required=False, allow_blank=True, default="")
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    role_id = serializers.UUIDField(required=False, allow_null=True)


class OrganizationInviteReadSerializer(serializers.ModelSerializer):
    expires_at = serializers.DateTimeField(source="profile_expires_at", read_only=True)
    role_name = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationInvite
        fields = [
            "id",
            "email",
            "name",
            "bio",
            "intake",
            "role_id",
            "role_name",
            "expires_at",
            "status",
            "invite_expires_at",
            "created_at",
            "accepted_at",
        ]

    def get_role_name(self, obj):
        return obj.role.name if obj.role_id else None

class InviteSignupSerializer(serializers.Serializer):
    invite_token = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise ValidationError({"confirm_password": "Passwords do not match."})
        validate_password(attrs["password"])
        return attrs

class UserProfileSerializer(serializers.ModelSerializer):
    phone_numbers = serializers.JSONField(required=False)

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "user",
            "avatar_url",
            "bio",
            "sex",
            "age",
            "birthday",
            "name",
            "organization",
            "phone_numbers",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "organization",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["phone_numbers"] = normalize_phone_numbers(
            getattr(instance, "_phone_numbers", None)
        )
        return data

    def validate_phone_numbers(self, value):
        if value is None:
            return default_phone_numbers_list()
        try:
            return validate_phone_numbers_for_storage(value)
        except PydanticValidationError as exc:
            raise serializers.ValidationError(exc.errors()) from exc
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def update(self, instance, validated_data):
        initial = getattr(self, "initial_data", {}) or {}
        phone_numbers_provided = isinstance(initial, dict) and "phone_numbers" in initial
        phone_numbers = validated_data.pop("phone_numbers", serializers.empty)
        instance = super().update(instance, validated_data)
        if phone_numbers_provided:
            value = [] if phone_numbers is serializers.empty else phone_numbers
            if value is None:
                value = []
            instance.phone_numbers = value
            instance.save(update_fields=["_phone_numbers", "updated_at"])
        return instance

    def create(self, validated_data):
        phone_numbers = validated_data.pop("phone_numbers", None)
        instance = super().create(validated_data)
        if phone_numbers is not None:
            instance.phone_numbers = phone_numbers
            instance.save(update_fields=["_phone_numbers", "updated_at"])
        return instance

class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "profile"]

class OrganizationSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Organization
        fields = ["id", "name", "description", "owner", "timezone", "logo", "logo_url", "created_at", "updated_at"]
        read_only_fields = ["logo_url"]
    
    def get_logo_url(self, obj):
        if obj.logo:
            return obj.logo.url
        return None

class CredentialsManagerSerializer(serializers.ModelSerializer):
    class Meta:
        model = CredentialsManager
        fields = [
            "id",
            "organization",
            "openai_api_key",
            "anthropic_api_key",
            "pexels_api_key",
            "elevenlabs_api_key",
            "heygen_api_key",
            "created_at",
            "updated_at",
        ]

class BigOrganizationSerializer(serializers.ModelSerializer):
    credentials = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()
    has_compliance_assistant = serializers.SerializerMethodField()
    pld_access_enabled = serializers.BooleanField(read_only=True)

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "description",
            "owner",
            "timezone",
            "logo_url",
            "created_at",
            "updated_at",
            "credentials",
            "can_manage",
            "is_owner",
            "has_compliance_assistant",
            "pld_access_enabled",
        ]

    def get_credentials(self, obj):
        credentials = CredentialsManager.objects.get(organization=obj)
        return CredentialsManagerSerializer(credentials).data
    
    def get_logo_url(self, obj):
        if obj.logo:
            return obj.logo.url
        return None
    
    def get_is_owner(self, obj):
        """Verifica si el usuario actual es el owner de la organización"""
        request = self.context.get('request')
        if request and request.user:
            return obj.owner == request.user
        return False
    
    def get_can_manage(self, obj):
        """Verifica si el usuario actual puede gestionar la organización (es owner o tiene la feature flag)"""
        request = self.context.get('request')
        if request and request.user:
            if obj.owner == request.user:
                return True
            from .services import FeatureFlagService
            enabled, _ = FeatureFlagService.is_feature_enabled(
                feature_flag_name="manage-organization",
                organization=obj,
                user=request.user
            )
            return enabled
        return False

    def get_has_compliance_assistant(self, obj):
        from api.ai_layers.compliance_assistant import organization_has_compliance_assistant

        return organization_has_compliance_assistant(obj)

class FeatureFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureFlag
        fields = ["id", "name", "created", "modified"]

class FeatureFlagAssignmentSerializer(serializers.ModelSerializer):
    feature_flag = FeatureFlagSerializer(read_only=True)
    feature_flag_id = serializers.PrimaryKeyRelatedField(
        queryset=FeatureFlag.objects.all(), source="feature_flag", write_only=True, required=False
    )

    class Meta:
        model = FeatureFlagAssignment
        fields = [
            "id",
            "organization",
            "user",
            "feature_flag",
            "feature_flag_id",
            "enabled",
            "created",
            "modified",
        ]

class FeatureFlagStatusResponseSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    feature_flag_name = serializers.CharField()
    reason = serializers.CharField()

class TeamFeatureFlagsResponseSerializer(serializers.Serializer):
    feature_flags = serializers.DictField(child=serializers.BooleanField())

class PublicOrganizationSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ["id", "name", "description", "logo_url"]

    def get_logo_url(self, obj):
        if obj.logo:
            return obj.logo.url
        return None

class OrganizationMemberSerializer(serializers.Serializer):
    """Read-only representation of an organization member for list API."""

    id = serializers.IntegerField()
    email = serializers.EmailField()
    username = serializers.CharField()
    profile_name = serializers.CharField(allow_blank=True, required=False)
    bio = serializers.CharField(allow_blank=True, required=False)
    is_owner = serializers.BooleanField()
    is_active = serializers.BooleanField(default=True)
    expires_at = serializers.CharField(allow_null=True, required=False)
    current_role = serializers.DictField(allow_null=True, required=False)

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "name", "description", "enabled", "capabilities", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

class RoleCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["name", "description", "enabled", "capabilities"]

    def validate_name(self, value):
        org = self.context.get("organization")
        if not org:
            return value
        qs = Role.objects.filter(organization=org, name=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("A role with this name already exists in this organization.")
        return value

    def validate_capabilities(self, value):
        if not value:
            return value
        org_only_flags = set(
            FeatureFlag.objects.filter(
                name__in=value, organization_only=True
            ).values_list("name", flat=True)
        )
        if org_only_flags:
            names = ", ".join(sorted(org_only_flags))
            raise ValidationError(
                f"The following flags are organization-only and cannot be used as role capabilities: {names}"
            )
        return value

    def create(self, validated_data):
        org = self.context.get("organization")
        if not org:
            raise ValidationError("Organization is required")
        validated_data.pop("organization", None)
        return Role.objects.create(organization=org, **validated_data)

class RoleAssignmentSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.name", read_only=True)

    class Meta:
        model = RoleAssignment
        fields = ["id", "user", "organization", "role", "role_name", "from_date", "to_date", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

class RoleAssignmentCreateSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    role_id = serializers.UUIDField()
    from_date = serializers.DateField(required=False)
    to_date = serializers.DateField(required=False, allow_null=True)
