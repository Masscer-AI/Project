from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Organization, CredentialsManager, UserProfile, FeatureFlag, FeatureFlagAssignment
from rest_framework.exceptions import ValidationError
from django.db import transaction


class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(required=True)
    organization_id = serializers.UUIDField(required=True, write_only=True)

    class Meta:
        model = User
        fields = ["username", "email", "password", "organization_id"]

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

    def create(self, validated_data):
        organization_id = validated_data.pop('organization_id')
        with transaction.atomic():
            user = User.objects.create_user(
                username=validated_data["username"],
                email=validated_data["email"],
                password=validated_data["password"],
            )

            # Prefer the org already validated (see validate_organization_id)
            organization = getattr(self, "_organization", None)
            if organization is None:
                organization = Organization.objects.select_for_update().get(id=organization_id)

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
    class Meta:
        model = Organization
        fields = ["id", "name", "description", "owner", "timezone", "created_at", "updated_at"]


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


    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "description",
            "owner",
            "timezone",
            "created_at",
            "updated_at",
            "credentials",
        ]

    def get_credentials(self, obj):
        credentials = CredentialsManager.objects.get(organization=obj)
        return CredentialsManagerSerializer(credentials).data


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
    class Meta:
        model = Organization
        fields = ["id", "name", "description"]
