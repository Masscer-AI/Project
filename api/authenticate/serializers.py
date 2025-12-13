from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Organization, CredentialsManager, UserProfile, FeatureFlag, FeatureFlagAssignment
from django.core.exceptions import ValidationError


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
            organization = Organization.objects.get(id=value)
        except Organization.DoesNotExist:
            raise ValidationError("Organization does not exist.")
        return value

    def create(self, validated_data):
        organization_id = validated_data.pop('organization_id')
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )
        
        # Assign organization to user's profile
        # UserProfile is created automatically by signal, but we need to assign the organization
        user_profile = UserProfile.objects.get(user=user)
        organization = Organization.objects.get(id=organization_id)
        user_profile.organization = organization
        user_profile.save()
        
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
        fields = ["id", "name", "description", "owner", "created_at", "updated_at"]


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
