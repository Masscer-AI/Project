from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Organization, OrganizationMember, CredentialsManager, UserProfile
from django.core.exceptions import ValidationError


class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )
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


class OrganizationMemberSerializer(serializers.ModelSerializer):

    class Meta:
        model = OrganizationMember
        fields = ["id", "organization", "user", "created_at", "updated_at"]


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
