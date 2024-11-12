from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Organization, OrganizationMember, CredentialsManager

class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        return user

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'email']


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['id', 'name', 'description', 'owner', 'created_at', 'updated_at']

class OrganizationMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationMember
        fields = ['id', 'organization', 'user', 'created_at', 'updated_at']

class CredentialsManagerSerializer(serializers.ModelSerializer):
    class Meta:
        model = CredentialsManager
        fields = ['id', 'organization', 'openai_api_key', 'brave_api_key', 
                  'anthropic_api_key', 'pexels_api_key', 'created_at', 'updated_at']
