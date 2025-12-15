from rest_framework.views import APIView
import json
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from django.contrib.auth import authenticate, login
from .serializers import (
    SignupSerializer,
    LoginSerializer,
    UserSerializer,
    UserProfileSerializer,
    OrganizationSerializer,
    CredentialsManagerSerializer,
    BigOrganizationSerializer,
    FeatureFlagStatusResponseSerializer,
    TeamFeatureFlagsResponseSerializer,
)
from .models import Token, Organization, UserProfile, CredentialsManager
from .services import FeatureFlagService
from rest_framework.permissions import AllowAny
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from api.authenticate.decorators.token_required import token_required

from django.contrib.auth.models import User
from django.views import View
from django.core.cache import cache
from .models import FeatureFlagAssignment
from django.core.exceptions import ValidationError

# from api.utils.color_printer import printer


@method_decorator(csrf_exempt, name="dispatch")
class SignupAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        org_id = request.query_params.get('orgId')
        if not org_id:
            return Response(
                {"error": "orgId query parameter is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            organization = Organization.objects.get(id=org_id)
        except Organization.DoesNotExist:
            return Response(
                {"error": "Organization not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except (ValueError, ValidationError):
            return Response(
                {"error": "Invalid organization ID format"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = PublicOrganizationSerializer(organization)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "User created successfully"}, status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name="dispatch")
class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data["email"]
            password = serializer.validated_data["password"]
            try:
                user = User.objects.get(email=email)
                user = authenticate(username=user.username, password=password)
            except User.DoesNotExist:
                user = None

            if user is not None:
                login(request, user)
                token, created = Token.get_or_create(user=user, token_type="login")
                return Response(
                    {
                        "message": "Login successful",
                        "token": token.key,
                        "expires_at": token.expires_at,
                    },
                    status=status.HTTP_200_OK,
                )
            return Response(
                {"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class UserView(View):
    permission_classes = [AllowAny]
    CACHE_TIMEOUT = 86400

    def get(self, request, *args, **kwargs):
        # Generar una clave única para el caché basado en el usuario
        cache_key = f"user_data_{request.user.id}"
        cached_data = cache.get(cache_key)

        # Si los datos están en el caché, devolverlos directamente
        if cached_data:

            return JsonResponse(cached_data, status=status.HTTP_200_OK)

        # Si no hay datos en el caché, serializar y guardar en el caché
        serializer = UserSerializer(request.user)
        response_data = serializer.data
        cache.set(cache_key, response_data, timeout=self.CACHE_TIMEOUT)

        return JsonResponse(response_data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):
        data = json.loads(request.body)

        # Validar si el username está disponible
        if (
            User.objects.filter(username=data["username"])
            .exclude(id=request.user.id)
            .exists()
        ):
            return JsonResponse(
                {"error": "username-already-taken"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validar si el email está disponible
        if (
            User.objects.filter(email=data["email"])
            .exclude(id=request.user.id)
            .exists()
        ):
            return JsonResponse(
                {"error": "email-already-taken"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Actualizar los datos del usuario
        request.user.username = data["username"]
        request.user.email = data["email"]
        request.user.save()

        # Actualizar el perfil del usuario si se incluye en los datos
        if "profile" in data:
            profile = request.user.profile
            if not profile:
                profile = UserProfile.objects.create(
                    user=request.user, **data["profile"]
                )
            serializer = UserProfileSerializer(profile, data=data["profile"])
            if serializer.is_valid():
                serializer.save()

        # Invalidar y actualizar el caché con los nuevos datos
        cache_key = f"user_data_{request.user.id}"
        serializer = UserSerializer(request.user)
        response_data = serializer.data
        cache.set(cache_key, response_data, timeout=self.CACHE_TIMEOUT)

        return JsonResponse(
            {"message": "user-updated-successfully"}, status=status.HTTP_200_OK
        )


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class OrganizationView(View):
    def get(self, request):
        organizations = Organization.objects.filter(owner=request.user)
        serializer = BigOrganizationSerializer(organizations, many=True)
        return JsonResponse(serializer.data, safe=False)

    def delete(self, request, organization_id):
        organization = Organization.objects.get(id=organization_id)
        if organization.owner != request.user:
            return JsonResponse(
                {"error": "You are not the owner of this organization"},
                status=status.HTTP_403_FORBIDDEN,
            )
        organization.delete()
        return JsonResponse(
            {"message": "Organization deleted successfully"}, status=status.HTTP_200_OK
        )

    def post(self, request):
        try:
            data = json.loads(request.body)
            data["owner"] = request.user.id
            serializer = OrganizationSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return JsonResponse(
                    {"message": "Organization created successfully"},
                    status=status.HTTP_201_CREATED,
                )
            return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, organization_id):
        data = json.loads(request.body)
        organization = Organization.objects.get(id=organization_id)
        if organization.owner != request.user:
            return JsonResponse(
                {"error": "You are not the owner of this organization"},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = OrganizationSerializer(organization, data=data)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse(
                {"message": "Organization updated successfully"},
                status=status.HTTP_200_OK,
            )
        return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class OrganizationCredentialsView(View):
    def get(self, request, organization_id):
        organization = Organization.objects.get(id=organization_id)
        if organization.owner != request.user:
            return JsonResponse(
                {"error": "You are not the owner of this organization"},
                status=status.HTTP_403_FORBIDDEN,
            )
        credentials_manager = CredentialsManager.objects.get(organization=organization)
        serializer = CredentialsManagerSerializer(credentials_manager)
        return JsonResponse(serializer.data, safe=False)

    def put(self, request, organization_id):
        data = json.loads(request.body)
        organization = Organization.objects.get(id=organization_id)
        credentials_manager = CredentialsManager.objects.get(organization=organization)
        serializer = CredentialsManagerSerializer(credentials_manager, data=data)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse(
                {"message": "Credentials updated successfully"},
                status=status.HTTP_200_OK,
            )
        return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class FeatureFlagCheckView(View):
    """Check if a specific feature flag is enabled for the current user."""

    def get(self, request, feature_flag_name):
        user = request.user
        enabled = FeatureFlagService.is_feature_enabled(
            feature_flag_name=feature_flag_name, user=user
        )

        serializer = FeatureFlagStatusResponseSerializer({
            "enabled": enabled,
            "feature_flag_name": feature_flag_name,
        })
        return JsonResponse(serializer.data, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class FeatureFlagListView(View):
    """Get all feature flags for the user's organizations."""

    def get(self, request):
        user = request.user
        
        # Get all organizations where user is owner or member
        owned_orgs = Organization.objects.filter(owner=user)
        # Get organization from user profile
        member_orgs = Organization.objects.none()
        if hasattr(user, 'profile') and user.profile.organization:
            member_orgs = Organization.objects.filter(id=user.profile.organization.id)
        user_organizations = (owned_orgs | member_orgs).distinct()
        
        # Collect all feature flags from all user's organizations
        all_flags = {}
        for org in user_organizations:
            org_flags = FeatureFlagService.get_organization_feature_flags(org)
            # Merge flags (user-level flags take priority, but we're only getting org-level here)
            for flag_name, enabled in org_flags.items():
                if flag_name not in all_flags:
                    all_flags[flag_name] = enabled
                # If already exists, keep the first one (or could use OR logic)
        
        # Also check user-level flags
        user_assignments = FeatureFlagAssignment.objects.filter(
            user=user, organization__isnull=True
        ).select_related("feature_flag")
        
        for assignment in user_assignments:
            all_flags[assignment.feature_flag.name] = assignment.enabled

        serializer = TeamFeatureFlagsResponseSerializer({
            "feature_flags": all_flags,
        })
        return JsonResponse(serializer.data, status=status.HTTP_200_OK)
