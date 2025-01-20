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
)
from .models import Token, Organization, UserProfile, CredentialsManager
from rest_framework.permissions import AllowAny
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from api.authenticate.decorators.token_required import token_required
from django.contrib.auth.models import User
from django.views import View
from django.core.cache import cache

# from api.utils.color_printer import printer


@method_decorator(csrf_exempt, name="dispatch")
class SignupAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(
            {"message": "User created successfully"}, status=status.HTTP_201_CREATED
        )

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
        serializer = OrganizationSerializer(organizations, many=True)
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
