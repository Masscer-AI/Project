from rest_framework.views import APIView
import json
import os
import logging
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, JSONParser, FormParser
from django.http import JsonResponse
from django.http.multipartparser import MultiPartParser, MultiPartParserError
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
    PublicOrganizationSerializer,
    OrganizationMemberSerializer,
    RoleSerializer,
    RoleCreateUpdateSerializer,
    RoleAssignmentSerializer,
    RoleAssignmentCreateSerializer,
)
from .models import Token, Organization, UserProfile, CredentialsManager, Role, RoleAssignment, FeatureFlag
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q
from .services import FeatureFlagService
from .tasks import generate_organization_logo
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
                {"open_signup": True},
                status=status.HTTP_200_OK,
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
        
        serializer = PublicOrganizationSerializer(
            organization, context={"request": request}
        )
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

        # Cambiar la contraseña si se proporciona
        if data.get("current_password") and data.get("new_password"):
            if not request.user.check_password(data["current_password"]):
                return JsonResponse(
                    {"error": "current-password-incorrect"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if len(data["new_password"]) < 8:
                return JsonResponse(
                    {"error": "password-min-length"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            request.user.set_password(data["new_password"])

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
                # Si no hay logo y no tiene la feature flag, encolar generación async con Celery
                elif not self._can_manage_logo(request.user, organization):
                    generate_organization_logo.delay(str(organization.id))
                
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
        # Use print statements to ensure logs show in dev server output
        
        organization = Organization.objects.get(id=organization_id)
        if organization.owner != request.user:
            return JsonResponse(
                {"error": "You are not the owner of this organization"},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        # Verificar permisos
        can_manage = self._can_manage_logo(request.user, organization)
        is_owner = organization.owner == request.user
        
        # DEBUG: Log request info
        print(f"=== PUT Organization {organization_id} ===")
        print(f"Content-Type: {request.content_type}")
        print(f"is_owner: {is_owner}, can_manage: {can_manage}")
        
        # Manejar datos JSON o multipart
        if request.content_type and 'multipart/form-data' in request.content_type:
            # Django no parsea multipart en PUT, hay que hacerlo manualmente
            try:
                parser = MultiPartParser(request.META, request, request.upload_handlers)
                data, files = parser.parse()
                data = data.dict()
                logo_file = files.get('logo')
            except MultiPartParserError as e:
                print(f"Multipart parse error: {e}")
                data = request.POST.dict()
                logo_file = request.FILES.get('logo')
                files = request.FILES
            delete_logo = data.get('delete_logo') == 'true'
            print(f"Multipart data: {data}")
            print(f"Files: {list(files.keys())}")
        else:
            data = json.loads(request.body)
            logo_file = None
            delete_logo = data.get('delete_logo', False)
            print(f"JSON data: {data}")
        
        print(f"delete_logo={delete_logo} (type: {type(delete_logo)}), has_logo_file={logo_file is not None}")
        
        # Verificar permisos para nombre
        if 'name' in data and data.get('name') != organization.name:
            if not (is_owner or can_manage):
                return JsonResponse(
                    {"error": "You don't have permission to modify organization name."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        
        # Verificar permisos para logo
        if (logo_file or delete_logo) and not (is_owner or can_manage):
            return JsonResponse(
                {"error": "You don't have permission to modify organization logo."},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        # Guardar la ruta del logo anterior ANTES de cualquier cambio
        old_logo_path = None
        old_logo_name = None
        if organization.logo and organization.logo.name:
            old_logo_name = organization.logo.name
            try:
                old_logo_path = organization.logo.path
                print(f"Old logo: name={old_logo_name}, path={old_logo_path}")
            except Exception as e:
                print(f"Error getting logo path: {e}")
        
        # Actualizar campos de texto (name, description)
        if 'name' in data and (is_owner or can_manage):
            organization.name = data['name']
        if 'description' in data:
            organization.description = data.get('description', '')
        
        # Manejar cambios de logo
        if delete_logo:
            print(f">>> DELETING LOGO for organization {organization_id}")
            
            # Eliminar el archivo del disco
            if old_logo_path:
                if os.path.exists(old_logo_path):
                    try:
                        os.remove(old_logo_path)
                        print(f"Deleted file from disk: {old_logo_path}")
                    except OSError as e:
                        print(f"Failed to delete file {old_logo_path}: {e}")
                else:
                    print(f"File not found on disk: {old_logo_path}")
            
            # Limpiar el campo en el modelo
            print(f"Before: organization.logo = {organization.logo}")
            organization.logo = None
            print(f"After setting None: organization.logo = {organization.logo}")
            
            # Guardar con update_fields para asegurar que solo se actualiza el logo
            organization.save(update_fields=['logo', 'name', 'description', 'updated_at'])
            print(f"After save: organization.logo = {organization.logo}")
            
            # Verificar en la base de datos
            org_from_db = Organization.objects.get(id=organization_id)
            print(f"From DB: logo = {org_from_db.logo}, logo.name = {org_from_db.logo.name if org_from_db.logo else 'None'}")
        
        elif logo_file:
            print(f">>> UPLOADING NEW LOGO: {logo_file.name}, size={logo_file.size}")
            
            # Eliminar el archivo anterior del disco
            if old_logo_path and os.path.exists(old_logo_path):
                try:
                    os.remove(old_logo_path)
                    print(f"Deleted old file: {old_logo_path}")
                except OSError as e:
                    print(f"Failed to delete old file: {e}")
            
            # Asignar el nuevo logo directamente
            organization.logo = logo_file
            organization.save()
            print(f"New logo saved: {organization.logo.name if organization.logo else 'None'}")
        
        else:
            print(">>> No logo changes, updating text fields only")
            organization.save()
        
        # Refrescar desde la base de datos
        organization.refresh_from_db()
        print(f"After refresh_from_db: logo = {organization.logo.name if organization.logo else 'None'}")
        
        response_serializer = OrganizationSerializer(
            organization,
            context={'request': request}
        )
        response_data = response_serializer.data
        response_data["message"] = "Organization updated successfully"
        
        print(f"Response logo_url: {response_data.get('logo_url')}")
        print("=== END PUT Organization ===")
        
        return JsonResponse(
            response_data,
            status=status.HTTP_200_OK,
        )


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


def _can_manage_organization(user, organization):
    """Return True if user is owner or has manage-organization feature flag."""
    if organization.owner_id == user.id:
        return True
    return FeatureFlagService.is_feature_enabled(
        feature_flag_name="manage-organization",
        organization=organization,
        user=user,
    )


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class OrganizationMembersView(View):
    """List organization members (owner + users with profile.organization set)."""

    def get(self, request, organization_id):
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return JsonResponse(
                {"error": "Organization not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not _can_manage_organization(request.user, organization):
            return JsonResponse(
                {"error": "You do not have permission to view this organization's members"},
                status=status.HTTP_403_FORBIDDEN,
            )

        owner = organization.owner
        owner_profile = getattr(owner, "profile", None)
        today = timezone.now().date()
        active_assignments = RoleAssignment.objects.filter(
            organization=organization,
            from_date__lte=today,
        ).filter(
            Q(to_date__isnull=True) | Q(to_date__gte=today)
        ).select_related("role", "user").order_by("from_date")
        user_to_role = {}
        for a in active_assignments:
            if a.user_id not in user_to_role:
                user_to_role[a.user_id] = {
                    "id": str(a.role_id),
                    "name": a.role.name,
                    "assignment_id": str(a.id),
                }

        members_data = [
            {
                "id": owner.id,
                "email": owner.email or "",
                "username": owner.username or "",
                "profile_name": (owner_profile.name if owner_profile and owner_profile.name else "") or "",
                "is_owner": True,
                "current_role": user_to_role.get(owner.id),
            }
        ]
        seen_ids = {owner.id}

        for profile in UserProfile.objects.filter(organization=organization).select_related("user"):
            user = profile.user
            if user.id in seen_ids:
                continue
            seen_ids.add(user.id)
            members_data.append({
                "id": user.id,
                "email": user.email or "",
                "username": user.username or "",
                "profile_name": (profile.name or "").strip(),
                "is_owner": False,
                "current_role": user_to_role.get(user.id),
            })

        serializer = OrganizationMemberSerializer(members_data, many=True)
        return JsonResponse(serializer.data, safe=False)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class OrganizationRolesView(View):
    """List and create roles for an organization."""

    def get(self, request, organization_id):
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return JsonResponse({"error": "Organization not found"}, status=status.HTTP_404_NOT_FOUND)
        if not _can_manage_organization(request.user, organization):
            return JsonResponse({"error": "You do not have permission to manage roles"}, status=status.HTTP_403_FORBIDDEN)
        roles = Role.objects.filter(organization=organization).order_by("name")
        serializer = RoleSerializer(roles, many=True)
        return JsonResponse(serializer.data, safe=False)

    def post(self, request, organization_id):
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return JsonResponse({"error": "Organization not found"}, status=status.HTTP_404_NOT_FOUND)
        if not _can_manage_organization(request.user, organization):
            return JsonResponse({"error": "You do not have permission to manage roles"}, status=status.HTTP_403_FORBIDDEN)
        data = json.loads(request.body) if request.body else {}
        serializer = RoleCreateUpdateSerializer(data=data, context={"organization": organization})
        if serializer.is_valid():
            role = serializer.save(organization=organization)
            return JsonResponse(RoleSerializer(role).data, status=status.HTTP_201_CREATED)
        return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class OrganizationRoleDetailView(View):
    """Get, update, or delete a single role."""

    def get(self, request, organization_id, role_id):
        try:
            organization = Organization.objects.get(id=organization_id)
            role = Role.objects.get(id=role_id, organization=organization)
        except (Organization.DoesNotExist, Role.DoesNotExist):
            return JsonResponse({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        if not _can_manage_organization(request.user, organization):
            return JsonResponse({"error": "You do not have permission"}, status=status.HTTP_403_FORBIDDEN)
        return JsonResponse(RoleSerializer(role).data)

    def put(self, request, organization_id, role_id):
        try:
            organization = Organization.objects.get(id=organization_id)
            role = Role.objects.get(id=role_id, organization=organization)
        except (Organization.DoesNotExist, Role.DoesNotExist):
            return JsonResponse({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        if not _can_manage_organization(request.user, organization):
            return JsonResponse({"error": "You do not have permission"}, status=status.HTTP_403_FORBIDDEN)
        data = json.loads(request.body) if request.body else {}
        serializer = RoleCreateUpdateSerializer(role, data=data, partial=True, context={"organization": organization})
        if serializer.is_valid():
            serializer.save()
            return JsonResponse(RoleSerializer(role).data)
        return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, organization_id, role_id):
        try:
            organization = Organization.objects.get(id=organization_id)
            role = Role.objects.get(id=role_id, organization=organization)
        except (Organization.DoesNotExist, Role.DoesNotExist):
            return JsonResponse({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        if not _can_manage_organization(request.user, organization):
            return JsonResponse({"error": "You do not have permission"}, status=status.HTTP_403_FORBIDDEN)
        role.delete()
        return JsonResponse({"message": "Role deleted"}, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class OrganizationRoleAssignmentsView(View):
    """Create or list role assignments. DELETE to remove an assignment."""

    def get(self, request, organization_id):
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return JsonResponse({"error": "Organization not found"}, status=status.HTTP_404_NOT_FOUND)
        if not _can_manage_organization(request.user, organization):
            return JsonResponse({"error": "You do not have permission"}, status=status.HTTP_403_FORBIDDEN)
        assignments = RoleAssignment.objects.filter(organization=organization).select_related("role", "user").order_by("-created_at")
        serializer = RoleAssignmentSerializer(assignments, many=True)
        data = [dict(d) for d in serializer.data]
        for i, a in enumerate(assignments):
            data[i]["user_id"] = a.user_id
        return JsonResponse(data, safe=False)

    def post(self, request, organization_id):
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return JsonResponse({"error": "Organization not found"}, status=status.HTTP_404_NOT_FOUND)
        if not _can_manage_organization(request.user, organization):
            return JsonResponse({"error": "You do not have permission"}, status=status.HTTP_403_FORBIDDEN)
        data = json.loads(request.body) if request.body else {}
        ser = RoleAssignmentCreateSerializer(data=data)
        if not ser.is_valid():
            return JsonResponse(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        role = Role.objects.filter(id=ser.validated_data["role_id"], organization=organization).first()
        if not role:
            return JsonResponse({"error": "Role not found"}, status=status.HTTP_404_NOT_FOUND)
        user = User.objects.filter(id=ser.validated_data["user_id"]).first()
        if not user:
            return JsonResponse({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        today = timezone.now().date()
        from_date = ser.validated_data.get("from_date") or today
        to_date = ser.validated_data.get("to_date")
        active = RoleAssignment.objects.filter(
            user=user, organization=organization
        ).filter(Q(to_date__isnull=True) | Q(to_date__gte=today)).first()
        if active:
            active.role = role
            active.from_date = from_date
            active.to_date = to_date
            active.save()
            assignment = active
        else:
            assignment = RoleAssignment.objects.create(
                user=user, organization=organization, role=role, from_date=from_date, to_date=to_date
            )
        return JsonResponse(RoleAssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED)

    def delete(self, request, organization_id):
        assignment_id = request.GET.get("assignment_id") or (json.loads(request.body) if request.body else {}).get("assignment_id")
        if not assignment_id:
            return JsonResponse({"error": "assignment_id required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            assignment = RoleAssignment.objects.get(id=assignment_id, organization_id=organization_id)
        except RoleAssignment.DoesNotExist:
            return JsonResponse({"error": "Assignment not found"}, status=status.HTTP_404_NOT_FOUND)
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return JsonResponse({"error": "Organization not found"}, status=status.HTTP_404_NOT_FOUND)
        if not _can_manage_organization(request.user, organization):
            return JsonResponse({"error": "You do not have permission"}, status=status.HTTP_403_FORBIDDEN)
        assignment.delete()
        return JsonResponse({"message": "Assignment removed"}, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class FeatureFlagNamesView(View):
    """List feature flag names (for role capabilities)."""

    CACHE_TIMEOUT = 86400  # 24 hours

    def get(self, request):
        cache_key = "feature_flag_names"
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return JsonResponse(cached_data, safe=False)

        flags = list(
            FeatureFlag.objects.order_by("name").values("name", "organization_only")
        )
        cache.set(cache_key, flags, timeout=self.CACHE_TIMEOUT)
        return JsonResponse(flags, safe=False)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class FeatureFlagCheckView(View):
    """Check if a specific feature flag is enabled for the current user."""

    CACHE_TIMEOUT = 86400  # 24 hours

    def get(self, request, feature_flag_name):
        user = request.user
        cache_key = f"ff_check_{user.id}_{feature_flag_name}"
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return JsonResponse(cached_data, status=status.HTTP_200_OK)

        enabled = FeatureFlagService.is_feature_enabled(
            feature_flag_name=feature_flag_name, user=user
        )

        serializer = FeatureFlagStatusResponseSerializer({
            "enabled": enabled,
            "feature_flag_name": feature_flag_name,
        })
        response_data = serializer.data
        cache.set(cache_key, response_data, timeout=self.CACHE_TIMEOUT)
        return JsonResponse(response_data, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class FeatureFlagListView(View):
    """Get all feature flags for the user's organizations."""

    CACHE_TIMEOUT = 86400  # 24 hours

    def get(self, request):
        user = request.user
        cache_key = f"ff_list_{user.id}"
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return JsonResponse(cached_data, status=status.HTTP_200_OK)

        # Get all organizations where user is owner or member
        owned_orgs = Organization.objects.filter(owner=user)

        # Organization owners get ALL feature flags enabled
        if owned_orgs.exists():
            all_flags = {
                flag.name: True
                for flag in FeatureFlag.objects.all()
            }
            serializer = TeamFeatureFlagsResponseSerializer({
                "feature_flags": all_flags,
            })
            response_data = serializer.data
            cache.set(cache_key, response_data, timeout=self.CACHE_TIMEOUT)
            return JsonResponse(response_data, status=status.HTTP_200_OK)

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
        response_data = serializer.data
        cache.set(cache_key, response_data, timeout=self.CACHE_TIMEOUT)
        return JsonResponse(response_data, status=status.HTTP_200_OK)
