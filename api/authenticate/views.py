from rest_framework.views import APIView
import json
import os
import logging
import requests
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, JSONParser, FormParser
from django.http import JsonResponse
from django.contrib.auth import authenticate, login
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
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
    PublicOrganizationSerializer
)
from .models import Token, Organization, UserProfile, CredentialsManager
from .services import FeatureFlagService
from api.utils.openai_functions import generate_image
from rest_framework.permissions import AllowAny
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from api.authenticate.decorators.token_required import token_required

from django.contrib.auth.models import User
from django.views import View
from django.core.cache import cache
from .models import FeatureFlagAssignment
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

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
    FEATURE_FLAG_NAME = "manage-organization"
    
    def _can_manage_logo(self, user, organization):
        """Verifica si el usuario puede gestionar el logo y nombre de la organización"""
        return FeatureFlagService.is_feature_enabled(
            feature_flag_name=self.FEATURE_FLAG_NAME,
            organization=organization,
            user=user
        )
    
    def _generate_logo_with_ai(self, organization):
        """Genera un logo automáticamente usando DALL-E-3"""
        try:
            # Obtener la API key de OpenAI desde CredentialsManager
            credentials = CredentialsManager.objects.get(organization=organization)
            api_key = credentials.openai_api_key
            
            if not api_key:
                # Si no hay API key configurada, usar la del entorno
                api_key = os.environ.get("OPENAI_API_KEY")
            
            if not api_key:
                return False, "OpenAI API key not configured"
            
            # Generar prompt para el logo
            prompt = f"A modern, professional logo for {organization.name}. "
            if organization.description:
                prompt += f"The organization is about: {organization.description}. "
            prompt += "Simple, clean design with a transparent or solid background. Suitable for business use."
            
            # Generar imagen con DALL-E-3
            image_url = generate_image(
                prompt=prompt,
                model="dall-e-3",
                size="1024x1024",
                quality="standard",
                api_key=api_key
            )
            
            # Descargar la imagen desde la URL
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            # Guardar la imagen como logo de la organización
            img_temp = NamedTemporaryFile(delete=True)
            img_temp.write(response.content)
            img_temp.flush()
            
            # Obtener extensión del archivo (DALL-E-3 devuelve PNG)
            ext = 'png'
            filename = f"{organization.id}.{ext}"
            
            organization.logo.save(filename, File(img_temp), save=True)
            img_temp.close()
            
            return True, "Logo generated successfully"
            
        except CredentialsManager.DoesNotExist:
            return False, "Credentials manager not found"
        except Exception as e:
            logger.error(f"Error generating logo for organization {organization.id}: {str(e)}")
            return False, f"Error generating logo: {str(e)}"
    
    def get(self, request):
        # Obtener organizaciones donde el usuario es owner
        owned_orgs = Organization.objects.filter(owner=request.user)
        
        # Obtener organizaciones donde el usuario es miembro (a través de su profile)
        member_orgs = Organization.objects.none()
        if hasattr(request.user, 'profile') and request.user.profile.organization:
            member_orgs = Organization.objects.filter(id=request.user.profile.organization.id)
        
        # Combinar ambas y eliminar duplicados
        organizations = (owned_orgs | member_orgs).distinct()
        
        serializer = BigOrganizationSerializer(
            organizations, 
            many=True,
            context={'request': request}
        )
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
            # Manejar datos JSON o multipart
            if request.content_type and 'multipart/form-data' in request.content_type:
                data = request.POST.dict()
                logo_file = request.FILES.get('logo')
            else:
                data = json.loads(request.body)
                logo_file = None
            
            data["owner"] = request.user.id
            serializer = OrganizationSerializer(
                data=data,
                context={'request': request}
            )
            
            if serializer.is_valid():
                organization = serializer.save()
                
                # El usuario que crea la organización siempre es el owner, así que puede gestionar el logo
                # Si hay archivo de logo, actualizarlo
                if logo_file:
                    organization.logo = logo_file
                    organization.save()
                # Si no hay logo y no tiene la feature flag, generar uno automáticamente
                elif not self._can_manage_logo(request.user, organization):
                    success, message = self._generate_logo_with_ai(organization)
                    if not success:
                        # Log el error pero continuar (la organización se creó sin logo)
                        logger.warning(f"Failed to generate logo for organization {organization.id}: {message}")
                
                response_serializer = OrganizationSerializer(
                    organization, 
                    context={'request': request}
                )
                response_data = response_serializer.data
                response_data["message"] = "Organization created successfully"
                return JsonResponse(
                    response_data,
                    status=status.HTTP_201_CREATED,
                )
            return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, organization_id):
        organization = Organization.objects.get(id=organization_id)
        if organization.owner != request.user:
            return JsonResponse(
                {"error": "You are not the owner of this organization"},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        # Verificar permisos para gestionar logo y nombre (feature flag)
        can_manage = self._can_manage_logo(request.user, organization)
        # Los owners siempre pueden gestionar, independientemente de la feature flag
        is_owner = organization.owner == request.user
        
        # Manejar datos JSON o multipart
        if request.content_type and 'multipart/form-data' in request.content_type:
            data = request.POST.dict()
            logo_file = request.FILES.get('logo')
            delete_logo = data.get('delete_logo') == 'true'
        else:
            data = json.loads(request.body)
            logo_file = None
            delete_logo = data.get('delete_logo', False)
        
        # Verificar si es owner (los owners siempre pueden gestionar)
        is_owner = organization.owner == request.user
        
        # Verificar si se intenta modificar el nombre sin permisos (solo si no es owner)
        if 'name' in data and data.get('name') != organization.name:
            if not (is_owner or can_manage):
                return JsonResponse(
                    {"error": "You don't have permission to modify organization name. You must be the owner or have the 'manage-organization' feature flag."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        
        # Si se intenta modificar o eliminar el logo sin permisos (solo si no es owner)
        if (logo_file or delete_logo) and not (is_owner or can_manage):
            return JsonResponse(
                {"error": "You don't have permission to modify organization logo. You must be the owner or have the 'manage-organization' feature flag."},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        # Guardar referencia al logo anterior ANTES de cualquier cambio
        old_logo = organization.logo
        
        # Si se solicita eliminar el logo
        if delete_logo:
            if old_logo:
                # Eliminar el archivo del sistema de archivos
                old_logo.delete(save=False)
                organization.logo = None
                organization.save()
            
            # Actualizar otros campos si se enviaron (excepto nombre si no tiene permisos)
            update_data = data.copy()
            if 'name' in update_data and not (is_owner or can_manage):
                # Remover nombre de los datos si no tiene permisos para cambiarlo
                update_data.pop('name')
            
            serializer = OrganizationSerializer(
                organization,
                data=update_data,
                partial=True,
                context={'request': request}
            )
            if serializer.is_valid():
                organization = serializer.save()
                response_serializer = OrganizationSerializer(
                    organization,
                    context={'request': request}
                )
                response_data = response_serializer.data
                response_data["message"] = "Logo deleted successfully" if old_logo else "Organization updated successfully"
                return JsonResponse(
                    response_data,
                    status=status.HTTP_200_OK,
                )
            return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Remover nombre de los datos si no tiene permisos para cambiarlo
        update_data = data.copy()
        if 'name' in update_data and not (is_owner or can_manage) and update_data.get('name') != organization.name:
            update_data.pop('name')
        
        serializer = OrganizationSerializer(
            organization, 
            data=update_data, 
            partial=True,
            context={'request': request}
        )
        
        if serializer.is_valid():
            organization = serializer.save()
            
            # Si hay nuevo archivo de logo, reemplazar el anterior
            if logo_file:
                # Eliminar logo anterior si existe (del sistema de archivos)
                if old_logo:
                    old_logo.delete(save=False)
                organization.logo = logo_file
                organization.save()
            
            response_serializer = OrganizationSerializer(
                organization,
                context={'request': request}
            )
            response_data = response_serializer.data
            response_data["message"] = "Organization updated successfully"
            return JsonResponse(
                response_data,
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
        import logging
        logger = logging.getLogger(__name__)
        
        user = request.user
        enabled = FeatureFlagService.is_feature_enabled(
            feature_flag_name=feature_flag_name, user=user
        )
        
        # Debug logging
        user_org = None
        if hasattr(user, 'profile') and user.profile.organization:
            user_org = user.profile.organization
        
        logger.info(f"🔍 Feature Flag Check Debug: user={user.email}, flag={feature_flag_name}, enabled={enabled}, org={user_org.name if user_org else None}")

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
