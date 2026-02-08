from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Organization, CredentialsManager, UserProfile, FeatureFlag, FeatureFlagAssignment, Role, RoleAssignment
from rest_framework.exceptions import ValidationError
from django.db import transaction


class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    email = serializers.EmailField(required=True)
    organization_id = serializers.UUIDField(required=False, write_only=True)
    organization_name = serializers.CharField(required=False, write_only=True, max_length=255)

    class Meta:
        model = User
        fields = ["username", "email", "password", "organization_id", "organization_name"]

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

        with transaction.atomic():
            user = User.objects.create_user(
                username=validated_data["username"],
                email=validated_data["email"],
                password=validated_data["password"],
            )

            if organization_name:
                # New independent signup: create org with user as owner
                organization = Organization.objects.create(
                    name=organization_name,
                    owner=user,
                )
            else:
                # Invited signup: join existing org
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


class UserProfileSerializer(serializers.ModelSerializer):
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
            "created_at",
            "updated_at",
        ]


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
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.logo.url)
            return obj.logo.url
        return None


class CredentialsManagerSerializer(serializers.ModelSerializer):
    class Meta:
        model = CredentialsManager
        fields = [
            "id",
            "organization",
            "openai_api_key",
            "brave_api_key",
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
        ]

    def get_credentials(self, obj):
        credentials = CredentialsManager.objects.get(organization=obj)
        return CredentialsManagerSerializer(credentials).data
    
    def get_logo_url(self, obj):
        if obj.logo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.logo.url)
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
            # Los owners siempre pueden gestionar
            if obj.owner == request.user:
                return True
            # Si no es owner, verificar la feature flag
            from .services import FeatureFlagService
            return FeatureFlagService.is_feature_enabled(
                feature_flag_name="manage-organization",
                organization=obj,
                user=request.user
            )
        return False


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


class TeamFeatureFlagsResponseSerializer(serializers.Serializer):
    feature_flags = serializers.DictField(child=serializers.BooleanField())


class PublicOrganizationSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ["id", "name", "description", "logo_url"]

    def get_logo_url(self, obj):
        if obj.logo:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.logo.url)
            return obj.logo.url
        return None


class OrganizationMemberSerializer(serializers.Serializer):
    """Read-only representation of an organization member for list API."""

    id = serializers.IntegerField()
    email = serializers.EmailField()
    username = serializers.CharField()
    profile_name = serializers.CharField(allow_blank=True, required=False)
    is_owner = serializers.BooleanField()
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
