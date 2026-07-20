from rest_framework.views import APIView
import json
import os
import logging
import pytz
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, JSONParser, FormParser
from django.http import JsonResponse
from django.http.multipartparser import MultiPartParser, MultiPartParserError
from django.contrib.auth import authenticate, login
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from .serializers import (
    SignupSerializer,
    LoginSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    UserSerializer,
    UserProfileSerializer,
    OrganizationSerializer,
    BigOrganizationSerializer,
    FeatureFlagStatusResponseSerializer,
    TeamFeatureFlagsResponseSerializer,
    PublicOrganizationSerializer,
    OrganizationMemberSerializer,
    RoleSerializer,
    RoleCreateUpdateSerializer,
    RoleAssignmentSerializer,
    RoleAssignmentCreateSerializer,
    OrganizationInviteCreateSerializer,
    OrganizationInviteReadSerializer,
    InviteSignupSerializer,
)
from .models import (
    Token,
    Organization,
    OrganizationTenant,
    UserProfile,
    Role,
    RoleAssignment,
    FeatureFlag,
    OrganizationInvite,
    hash_organization_invite_token,
)
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q
from django.db import transaction
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
from .feature_flags_registry import KNOWN_FEATURE_FLAGS
from django.core.exceptions import ValidationError
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from api.utils.email_service import EmailService
import requests as http_requests

from .auth_handoff import create_handoff_code, exchange_handoff_code, issue_login_token_for_handoff
from .subdomain_utils import (
    extract_subdomain,
    validate_auth_return_to_origin,
    validate_google_auth_redirect_uri,
    validate_subdomain,
)
from .tenant_schemas import validate_tenant_theme
from .tenant_favicon import regenerate_tenant_favicon_from_logo, clear_tenant_favicon
from .tenant_services import (
    build_public_tenant_config,
    get_or_create_tenant,
    get_tenant_for_organization,
    get_user_organization,
    serialize_tenant_for_manage,
    user_from_optional_auth_header,
)
from .tenant_portal_access import (
    check_tenant_portal_signup_allowed,
    check_user_tenant_portal_access,
    get_portal_origin_from_data,
)
from api.payments.models import Subscription
from django.db import IntegrityError

logger = logging.getLogger(__name__)

ORG_INVITE_VALID_DAYS = 7


def _exchange_google_auth_code(code: str, redirect_uri: str) -> str | None:
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        logger.error("[Google Login] GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET not configured")
        return None
    logger.info(
        "[Google Login] Exchanging auth code (redirect_uri=%s, client_id=%s…)",
        redirect_uri,
        client_id[:20],
    )
    try:
        token_resp = http_requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        if not token_resp.ok:
            logger.error(
                "[Google Login] Token exchange failed: status=%s body=%s redirect_uri=%s",
                token_resp.status_code,
                token_resp.text,
                redirect_uri,
            )
            return None
        return token_resp.json().get("access_token")
    except Exception as e:
        logger.error("[Google Login] Failed to exchange auth code: %s", e, exc_info=True)
        return None


def _resolve_google_access_token(request) -> tuple[str | None, Response | None]:
    access_token = (request.data.get("access_token") or "").strip()
    if access_token:
        return access_token, None

    code = (request.data.get("code") or "").strip()
    if not code:
        return None, Response(
            {"error": "access_token or code is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    redirect_uri = validate_google_auth_redirect_uri(request.data.get("redirect_uri") or "")
    if not redirect_uri:
        return None, Response(
            {"error": "A valid redirect_uri is required for code exchange"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    exchanged = _exchange_google_auth_code(code, redirect_uri)
    if not exchanged:
        return None, Response(
            {"error": "Invalid or expired Google authorization code"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    return exchanged, None


def _frontend_base_url(request):
    frontend_url = getattr(settings, "FRONTEND_URL", "").rstrip("/")
    if not frontend_url:
        scheme = "https" if request.is_secure() else "http"
        frontend_url = f"{scheme}://{request.get_host()}"
    return frontend_url


def _send_organization_invite_email(request, *, invite_email: str, organization_name: str, signup_url: str) -> None:
    html = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.5;">
            <h2>You have been invited</h2>
            <p>You have been invited to join <strong>{organization_name}</strong> on Masscer.</p>
            <p>
                <a href="{signup_url}" style="display:inline-block;padding:10px 16px;background:#6e5bff;color:#fff;text-decoration:none;border-radius:6px;">
                    Accept invitation
                </a>
            </p>
            <p>If the button does not work, open this link:</p>
            <p><a href="{signup_url}">{signup_url}</a></p>
            <p>If you did not expect this email, you can ignore it.</p>
        </div>
    """.strip()
    email_service = EmailService()
    email_service.send_email(
        to=invite_email,
        subject=f"Invitation to join {organization_name}",
        html=html,
        from_name="Masscer",
    )

# from api.utils.color_printer import printer


@method_decorator(csrf_exempt, name="dispatch")
class SignupAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # No auth before signup; avoids DRF SessionAuthentication CSRF

    def get(self, request):
        invite_token = request.query_params.get("invite")
        if invite_token:
            return self._signup_invite_get(request, invite_token.strip())

        org_id = request.query_params.get("orgId")
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
                status=status.HTTP_404_NOT_FOUND,
            )
        except (ValueError, ValidationError):
            return Response(
                {"error": "Invalid organization ID format"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PublicOrganizationSerializer(
            organization, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    def _signup_invite_get(self, request, invite_token: str):
        invite = OrganizationInvite.lookup_by_raw_token(invite_token)
        if not invite:
            return Response(
                {"invite_valid": False, "error": "invalid-or-expired-invite"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        invite.mark_expired_if_needed()
        invite.refresh_from_db()
        if invite.status != OrganizationInvite.Status.PENDING:
            return Response(
                {"invite_valid": False, "error": "invalid-or-expired-invite"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if invite.is_invite_expired():
            invite.mark_expired_if_needed()
            return Response(
                {"invite_valid": False, "error": "invalid-or-expired-invite"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email_registered = User.objects.filter(email__iexact=invite.email).exists()
        org_data = PublicOrganizationSerializer(
            invite.organization, context={"request": request}
        ).data
        return Response(
            {
                "invite_valid": not email_registered,
                "email_already_registered": email_registered,
                "organization": org_data,
                "email": invite.email,
                "name": invite.name or "",
                "bio": invite.bio or "",
                "expires_at": invite.profile_expires_at.isoformat()
                if invite.profile_expires_at
                else None,
                "invite_expires_at": invite.invite_expires_at.isoformat(),
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        if request.data.get("invite_token"):
            return self._post_invite_signup(request)

        signup_denied = check_tenant_portal_signup_allowed(request.data)
        if signup_denied is not None:
            return signup_denied

        serializer = SignupSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "User created successfully"}, status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def _post_invite_signup(self, request):
        serializer = InviteSignupSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        raw_token = serializer.validated_data["invite_token"].strip()
        password = serializer.validated_data["password"]

        invite = OrganizationInvite.lookup_by_raw_token(raw_token)
        if not invite:
            return Response(
                {"error": "invalid-or-expired-invite"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        signup_denied = check_tenant_portal_signup_allowed(
            request.data,
            invite_organization_id=invite.organization_id,
        )
        if signup_denied is not None:
            return signup_denied

        invite.mark_expired_if_needed()
        invite.refresh_from_db()
        if invite.status != OrganizationInvite.Status.PENDING:
            return Response(
                {"error": "invalid-or-expired-invite"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if invite.is_invite_expired():
            return Response(
                {"error": "invalid-or-expired-invite"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if User.objects.filter(email__iexact=invite.email).exists():
            return Response(
                {"error": "email-already-registered"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            invite_locked = OrganizationInvite.objects.select_for_update().get(pk=invite.pk)
            if invite_locked.status != OrganizationInvite.Status.PENDING:
                return Response(
                    {"error": "invalid-or-expired-invite"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            email = invite_locked.email
            base_username = email.split("@")[0]
            username = base_username
            suffix = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{suffix}"
                suffix += 1

            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
            )
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.organization = invite_locked.organization
            profile.name = invite_locked.name or ""
            profile.bio = invite_locked.bio or ""
            profile.expires_at = invite_locked.profile_expires_at
            profile.save()

            now = timezone.now()
            invite_locked.status = OrganizationInvite.Status.ACCEPTED
            invite_locked.accepted_at = now
            invite_locked.accepted_user = user
            invite_locked.save(
                update_fields=[
                    "status",
                    "accepted_at",
                    "accepted_user",
                    "updated_at",
                ]
            )

        return Response(
            {"message": "User created successfully"},
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_exempt, name="dispatch")
class LoginAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # No session/token before login; avoids DRF SessionAuthentication CSRF

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
                # Block deactivated or expired users from logging in
                profile = getattr(user, "profile", None)
                if profile and profile.organization_id and not profile.is_active:
                    return Response(
                        {"error": "Your account has been deactivated. Contact your organization administrator."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                if profile and profile.expires_at and profile.expires_at < timezone.now():
                    return Response(
                        {"error": "Your access has expired. Contact your organization administrator."},
                        status=status.HTTP_403_FORBIDDEN,
                    )

                portal_origin = get_portal_origin_from_data(request.data)
                portal_denied = check_user_tenant_portal_access(user, portal_origin)
                if portal_denied is not None:
                    return portal_denied

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
class GoogleLoginAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        import traceback

        access_token, token_error = _resolve_google_access_token(request)
        if token_error:
            return token_error

        logger.info("[Google Login] Fetching userinfo from Google")
        try:
            userinfo_resp = http_requests.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            logger.info("[Google Login] Google userinfo status: %s", userinfo_resp.status_code)
            logger.debug("[Google Login] Google userinfo body: %s", userinfo_resp.text)
            userinfo_resp.raise_for_status()
            id_info = userinfo_resp.json()
        except Exception as e:
            logger.error("[Google Login] Failed to fetch Google userinfo: %s\n%s", e, traceback.format_exc())
            return Response({"error": "Invalid Google token"}, status=status.HTTP_401_UNAUTHORIZED)

        google_email = id_info.get("email")
        google_name = id_info.get("name", "")
        google_picture = id_info.get("picture", "")
        logger.info("[Google Login] Google email=%s name=%s", google_email, google_name)

        if not google_email:
            logger.error("[Google Login] No email in Google userinfo response: %s", id_info)
            return Response({"error": "Could not retrieve email from Google"}, status=status.HTTP_400_BAD_REQUEST)

        return_to_raw = request.data.get("return_to")
        return_to_origin = validate_auth_return_to_origin(return_to_raw or "")

        try:
            user = User.objects.filter(email=google_email).first()

            if return_to_origin and user is None:
                logger.info(
                    "[Google Login] Blocked new signup for tenant handoff email=%s",
                    google_email,
                )
                return Response(
                    {
                        "error": (
                            "No account found for this email. "
                            "Contact your organization administrator for an invite."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            if user is None:
                logger.info("[Google Login] Creating new user for email=%s", google_email)
                base_username = google_email.split("@")[0]
                username = base_username
                suffix = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{suffix}"
                    suffix += 1

                user = User.objects.create_user(
                    username=username,
                    email=google_email,
                    password=None,
                    first_name=google_name.split(" ")[0] if google_name else "",
                    last_name=" ".join(google_name.split(" ")[1:]) if google_name else "",
                )
                logger.info("[Google Login] User created: id=%s username=%s", user.id, user.username)

                org = Organization.objects.create(name=f"{google_name or username}'s workspace", owner=user)
                logger.info("[Google Login] Organization created: id=%s", org.id)

                profile, created = UserProfile.objects.get_or_create(user=user)
                logger.info("[Google Login] UserProfile get_or_create: created=%s", created)
                profile.name = google_name
                profile.avatar_url = google_picture
                profile.organization = org
                profile.save()
                logger.info("[Google Login] UserProfile saved")
            else:
                logger.info("[Google Login] Existing user found: id=%s username=%s", user.id, user.username)
                profile = getattr(user, "profile", None)
                if profile and profile.organization_id and not profile.is_active:
                    return Response(
                        {"error": "Your account has been deactivated. Contact your organization administrator."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                if profile and profile.expires_at and profile.expires_at < timezone.now():
                    return Response(
                        {"error": "Your access has expired. Contact your organization administrator."},
                        status=status.HTTP_403_FORBIDDEN,
                    )

            portal_denied = check_user_tenant_portal_access(user, return_to_origin)
            if portal_denied is not None:
                return portal_denied

            token, _ = Token.get_or_create(user=user, token_type="login")
            logger.info("[Google Login] Token issued for user id=%s", user.id)

            if return_to_origin:
                handoff_code = create_handoff_code(user.id, return_to_origin)
                return Response(
                    {
                        "message": "Login successful",
                        "handoff_code": handoff_code,
                        "return_to": return_to_origin,
                    },
                    status=status.HTTP_200_OK,
                )

            return Response(
                {
                    "message": "Login successful",
                    "token": token.key,
                    "expires_at": token.expires_at,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error("[Google Login] Unexpected error: %s\n%s", e, traceback.format_exc())
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name="dispatch")
class AuthHandoffExchangeAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        code = (request.data.get("code") or "").strip()
        if not code:
            return Response({"error": "code is required"}, status=status.HTTP_400_BAD_REQUEST)

        result = exchange_handoff_code(code)
        if not result:
            return Response(
                {"error": "Invalid or expired handoff code"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user, return_to = result
        profile = getattr(user, "profile", None)
        if profile and profile.organization_id and not profile.is_active:
            return Response(
                {"error": "Your account has been deactivated. Contact your organization administrator."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if profile and profile.expires_at and profile.expires_at < timezone.now():
            return Response(
                {"error": "Your access has expired. Contact your organization administrator."},
                status=status.HTTP_403_FORBIDDEN,
            )

        portal_denied = check_user_tenant_portal_access(user, return_to)
        if portal_denied is not None:
            return portal_denied

        token = issue_login_token_for_handoff(user)
        return Response(
            {
                "token": token.key,
                "expires_at": token.expires_at,
            },
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class PasswordResetRequestAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        user = User.objects.filter(email__iexact=email).first()

        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)

            frontend_url = getattr(settings, "FRONTEND_URL", "").rstrip("/")
            if not frontend_url:
                scheme = "https" if request.is_secure() else "http"
                frontend_url = f"{scheme}://{request.get_host()}"

            reset_url = f"{frontend_url}/reset-password?uid={uid}&token={token}"

            html = f"""
                <div style="font-family: Arial, sans-serif; line-height: 1.5;">
                    <h2>Reset your password</h2>
                    <p>We received a request to reset your password.</p>
                    <p>
                        <a href="{reset_url}" style="display:inline-block;padding:10px 16px;background:#6e5bff;color:#fff;text-decoration:none;border-radius:6px;">
                            Reset Password
                        </a>
                    </p>
                    <p>If the button does not work, open this link:</p>
                    <p><a href="{reset_url}">{reset_url}</a></p>
                    <p>If you did not request this, you can safely ignore this email.</p>
                </div>
            """.strip()

            try:
                email_service = EmailService()
                email_service.send_email(
                    to=user.email,
                    subject="Reset your password",
                    html=html,
                    from_name="Masscer",
                )
            except Exception:
                logger.exception("Failed to send password reset email")

        return Response(
            {
                "message": "If an account with that email exists, a password reset link has been sent."
            },
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class PasswordResetConfirmAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uid = serializer.validated_data["uid"]
        token = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except Exception:
            return Response(
                {"error": "invalid-or-expired-reset-link"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not default_token_generator.check_token(user, token):
            return Response(
                {"error": "invalid-or-expired-reset-link"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save(update_fields=["password"])

        Token.objects.filter(user=user, token_type="login").delete()

        return Response(
            {"message": "Password reset successful."},
            status=status.HTTP_200_OK,
        )


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
        enabled, _ = FeatureFlagService.is_feature_enabled(
            feature_flag_name=self.FEATURE_FLAG_NAME,
            organization=organization,
            user=user
        )
        return enabled
    
    def get(self, request):
        # Obtener organizaciones donde el usuario es owner
        owned_orgs = Organization.objects.filter(owner=request.user)
        
        # Obtener organizaciones donde el usuario es miembro activo (a través de su profile)
        member_orgs = Organization.objects.none()
        if hasattr(request.user, 'profile') and request.user.profile.organization and request.user.profile.is_active:
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
        
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return JsonResponse(
                {"error": "Organization not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not _can_manage_organization(request.user, organization):
            return JsonResponse(
                {"error": "You don't have permission to manage this organization"},
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
        if 'timezone' in data and (is_owner or can_manage):
            tz_val = (data.get('timezone') or '').strip()
            if not tz_val:
                return JsonResponse(
                    {"error": "timezone cannot be empty"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if tz_val not in pytz.all_timezones:
                return JsonResponse(
                    {"error": f"Invalid timezone: {tz_val}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            organization.timezone = tz_val
        
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
            organization.save(update_fields=['logo', 'name', 'description', 'timezone', 'updated_at'])
            print(f"After save: organization.logo = {organization.logo}")
            _sync_tenant_favicon(organization)
            
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
            _sync_tenant_favicon(organization)
        
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


def _is_active_member(user, organization):
    """Return True if user is an active member (or owner) of the organization."""
    if organization.owner_id == user.id:
        return True
    profile = getattr(user, "profile", None)
    if profile and profile.organization_id == organization.id and profile.is_active:
        return True
    return False


def _can_manage_organization(user, organization):
    """Return True if user is owner or has manage-organization feature flag.
    Deactivated members are always rejected."""
    if not _is_active_member(user, organization):
        return False
    if organization.owner_id == user.id:
        return True
    enabled, _ = FeatureFlagService.is_feature_enabled(
        feature_flag_name="manage-organization",
        organization=organization,
        user=user,
    )
    return enabled


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
                "bio": (owner_profile.bio or "") if owner_profile else "",
                "is_owner": True,
                "is_active": True,
                "expires_at": None,
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
                "bio": (profile.bio or "").strip(),
                "is_owner": False,
                "is_active": profile.is_active,
                "expires_at": profile.expires_at.isoformat() if profile.expires_at else None,
                "current_role": user_to_role.get(user.id),
            })

        serializer = OrganizationMemberSerializer(members_data, many=True)
        return JsonResponse(serializer.data, safe=False)

    def post(self, request, organization_id):
        """Create a new user and add them directly to the organization."""
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return JsonResponse({"error": "Organization not found"}, status=status.HTTP_404_NOT_FOUND)

        if not _can_manage_organization(request.user, organization):
            return JsonResponse({"error": "You do not have permission"}, status=status.HTTP_403_FORBIDDEN)

        data = json.loads(request.body) if request.body else {}
        username = data.get("username", "").strip()
        email = data.get("email", "").strip()
        password = data.get("password", "")
        name = data.get("name", "").strip()
        bio = data.get("bio", "").strip()
        expires_at_raw = data.get("expires_at")

        if not username or not email or not password:
            return JsonResponse(
                {"error": "username, email and password are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(email=email).exists():
            return JsonResponse({"error": "Email already in use"}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=username).exists():
            return JsonResponse({"error": "Username already in use"}, status=status.HTTP_400_BAD_REQUEST)

        parsed_expires = None
        if expires_at_raw:
            from django.utils.dateparse import parse_datetime
            parsed_expires = parse_datetime(expires_at_raw)
            if parsed_expires is None:
                return JsonResponse(
                    {"error": "Invalid expires_at format, expected ISO 8601"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        with transaction.atomic():
            user = User.objects.create_user(username=username, email=email, password=password)
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.organization = organization
            profile.name = name
            profile.bio = bio
            profile.expires_at = parsed_expires
            profile.save()

        return JsonResponse(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "profile_name": profile.name,
                "bio": profile.bio,
                "is_owner": False,
                "is_active": profile.is_active,
                "expires_at": profile.expires_at.isoformat() if profile.expires_at else None,
                "current_role": None,
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class OrganizationInvitesView(View):
    """List (GET) or create + email (POST) organization member invites."""

    def get(self, request, organization_id):
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return JsonResponse(
                {"error": "Organization not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if not _can_manage_organization(request.user, organization):
            return JsonResponse(
                {"error": "You do not have permission"}, status=status.HTTP_403_FORBIDDEN
            )

        invites = OrganizationInvite.objects.filter(organization=organization).order_by(
            "-created_at"
        )[:200]
        serializer = OrganizationInviteReadSerializer(invites, many=True)
        return JsonResponse(serializer.data, safe=False)

    def post(self, request, organization_id):
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return JsonResponse(
                {"error": "Organization not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if not _can_manage_organization(request.user, organization):
            return JsonResponse(
                {"error": "You do not have permission"}, status=status.HTTP_403_FORBIDDEN
            )

        data = json.loads(request.body) if request.body else {}
        ser = OrganizationInviteCreateSerializer(data=data)
        if not ser.is_valid():
            return JsonResponse(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        normalized_email = ser.validated_data["email"].strip().lower()
        name = (ser.validated_data.get("name") or "").strip()
        bio = (ser.validated_data.get("bio") or "").strip()
        profile_expires_at = ser.validated_data.get("expires_at")

        if User.objects.filter(email__iexact=normalized_email).exists():
            return JsonResponse(
                {"error": "Email already registered"}, status=status.HTTP_400_BAD_REQUEST
            )

        now = timezone.now()
        invite_deadline = now + timezone.timedelta(days=ORG_INVITE_VALID_DAYS)
        raw_token = OrganizationInvite.generate_raw_token()
        digest = hash_organization_invite_token(raw_token)

        pending = OrganizationInvite.objects.filter(
            organization=organization,
            email__iexact=normalized_email,
            status=OrganizationInvite.Status.PENDING,
        ).first()

        if pending:
            pending.token_hash = digest
            pending.invite_expires_at = invite_deadline
            pending.name = name
            pending.bio = bio
            pending.profile_expires_at = profile_expires_at
            pending.invited_by = request.user
            pending.save()
            invite = pending
        else:
            invite = OrganizationInvite.objects.create(
                organization=organization,
                email=normalized_email,
                name=name,
                bio=bio,
                profile_expires_at=profile_expires_at,
                invited_by=request.user,
                token_hash=digest,
                status=OrganizationInvite.Status.PENDING,
                invite_expires_at=invite_deadline,
            )

        signup_url = f"{_frontend_base_url(request)}/signup?invite={raw_token}"
        try:
            from django.utils.html import escape

            _send_organization_invite_email(
                request,
                invite_email=normalized_email,
                organization_name=escape(organization.name),
                signup_url=signup_url,
            )
        except Exception:
            logger.exception("Failed to send organization invite email")
            return JsonResponse(
                {"error": "Failed to send invite email"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        out = OrganizationInviteReadSerializer(invite).data
        return JsonResponse(
            {"message": "Invitation sent", "invite": out},
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class OrganizationInviteDetailView(View):
    """Revoke (DELETE) a pending invite."""

    def delete(self, request, organization_id, invite_id):
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return JsonResponse(
                {"error": "Organization not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if not _can_manage_organization(request.user, organization):
            return JsonResponse(
                {"error": "You do not have permission"}, status=status.HTTP_403_FORBIDDEN
            )

        try:
            invite = OrganizationInvite.objects.get(
                id=invite_id, organization=organization
            )
        except OrganizationInvite.DoesNotExist:
            return JsonResponse(
                {"error": "Invite not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if invite.status != OrganizationInvite.Status.PENDING:
            return JsonResponse(
                {"error": "Invite cannot be revoked"}, status=status.HTTP_400_BAD_REQUEST
            )

        invite.status = OrganizationInvite.Status.CANCELLED
        invite.save(update_fields=["status", "updated_at"])
        return JsonResponse({"message": "Invitation cancelled"}, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class OrganizationMemberDetailView(View):
    """
    PATCH  → deactivate / reactivate a member  (body: {"is_active": bool})
    DELETE → fully remove a member from the organization
    """

    def patch(self, request, organization_id, user_id):
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return JsonResponse({"error": "Organization not found"}, status=status.HTTP_404_NOT_FOUND)

        if not _can_manage_organization(request.user, organization):
            return JsonResponse({"error": "You do not have permission"}, status=status.HTTP_403_FORBIDDEN)

        # Cannot deactivate the owner
        if organization.owner_id == user_id:
            return JsonResponse({"error": "Cannot deactivate the organization owner"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            profile = UserProfile.objects.select_related("user").get(
                user_id=user_id, organization=organization
            )
        except UserProfile.DoesNotExist:
            return JsonResponse({"error": "Member not found in this organization"}, status=status.HTTP_404_NOT_FOUND)

        data = json.loads(request.body) if request.body else {}
        update_fields = ["updated_at"]

        if "is_active" in data:
            new_status = data["is_active"]
            if not isinstance(new_status, bool):
                return JsonResponse({"error": "is_active must be a boolean"}, status=status.HTTP_400_BAD_REQUEST)
            profile.is_active = new_status
            update_fields.append("is_active")

        if "expires_at" in data:
            expires_at_raw = data["expires_at"]
            if expires_at_raw is None:
                profile.expires_at = None
            else:
                from django.utils.dateparse import parse_datetime
                parsed = parse_datetime(expires_at_raw)
                if parsed is None:
                    return JsonResponse(
                        {"error": "Invalid expires_at format, expected ISO 8601"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                profile.expires_at = parsed
            update_fields.append("expires_at")

        if "name" in data:
            profile.name = data["name"].strip()
            update_fields.append("name")

        if "bio" in data:
            profile.bio = data["bio"].strip()
            update_fields.append("bio")

        if len(update_fields) == 1:
            return JsonResponse({"error": "No valid fields provided"}, status=status.HTTP_400_BAD_REQUEST)

        profile.save(update_fields=update_fields)

        return JsonResponse(
            {
                "message": "Member updated successfully",
                "is_active": profile.is_active,
                "expires_at": profile.expires_at.isoformat() if profile.expires_at else None,
                "name": profile.name,
                "bio": profile.bio,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, organization_id, user_id):
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return JsonResponse({"error": "Organization not found"}, status=status.HTTP_404_NOT_FOUND)

        if not _can_manage_organization(request.user, organization):
            return JsonResponse({"error": "You do not have permission"}, status=status.HTTP_403_FORBIDDEN)

        # Cannot remove the owner
        if organization.owner_id == user_id:
            return JsonResponse({"error": "Cannot remove the organization owner"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            profile = UserProfile.objects.select_related("user").get(
                user_id=user_id, organization=organization
            )
        except UserProfile.DoesNotExist:
            return JsonResponse({"error": "Member not found in this organization"}, status=status.HTTP_404_NOT_FOUND)

        # --- Cleanup org-scoped data for this user ---
        from api.messaging.models import ConversationAlertRule, AlertSubscription

        # 1. Remove role assignments
        RoleAssignment.objects.filter(user_id=user_id, organization=organization).delete()

        # 2. Remove from alert rule selected_members (M2M)
        for rule in ConversationAlertRule.objects.filter(organization=organization):
            rule.selected_members.remove(profile.user)

        # 3. Remove alert subscriptions for this org's rules
        AlertSubscription.objects.filter(
            user_id=user_id,
            alert_rule__organization=organization,
        ).delete()

        # 4. Unlink profile from organization
        profile.organization = None
        profile.is_active = True  # Reset so user is clean if they join another org
        profile.save(update_fields=["organization", "is_active", "updated_at"])

        return JsonResponse({"message": "Member removed successfully"}, status=status.HTTP_200_OK)


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
        payload = json.loads(request.body) if request.body else {}
        assignment_id = request.GET.get("assignment_id") or payload.get("assignment_id")
        user_id_raw = request.GET.get("user_id") or payload.get("user_id")

        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return JsonResponse({"error": "Organization not found"}, status=status.HTTP_404_NOT_FOUND)

        if not _can_manage_organization(request.user, organization):
            return JsonResponse({"error": "You do not have permission"}, status=status.HTTP_403_FORBIDDEN)

        assignment = None
        if assignment_id:
            try:
                assignment = RoleAssignment.objects.get(
                    id=assignment_id, organization_id=organization_id
                )
            except RoleAssignment.DoesNotExist:
                return JsonResponse({"error": "Assignment not found"}, status=status.HTTP_404_NOT_FOUND)
        elif user_id_raw is not None:
            try:
                user_id_int = int(user_id_raw)
            except (TypeError, ValueError):
                return JsonResponse({"error": "user_id invalid"}, status=status.HTTP_400_BAD_REQUEST)
            today = timezone.now().date()
            assignment = (
                RoleAssignment.objects.filter(
                    organization_id=organization_id,
                    user_id=user_id_int,
                    from_date__lte=today,
                )
                .filter(Q(to_date__isnull=True) | Q(to_date__gte=today))
                .order_by("-from_date")
                .first()
            )
            if not assignment:
                return JsonResponse({"message": "No active assignment"}, status=status.HTTP_200_OK)
        else:
            return JsonResponse(
                {"error": "assignment_id or user_id required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignment.delete()
        return JsonResponse({"message": "Assignment removed"}, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class FeatureFlagNamesView(View):
    """List feature flag names (for role capabilities).

    Only returns flags from the registry (KNOWN_FEATURE_FLAGS).
    Flags not in the registry are admin-only and should not be
    assignable via roles.
    """

    def get(self, request):
        flags = sorted(
            [
                {"name": name, "organization_only": meta.get("organization_only", False)}
                for name, meta in KNOWN_FEATURE_FLAGS.items()
            ],
            key=lambda f: f["name"],
        )
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

        enabled, reason = FeatureFlagService.is_feature_enabled(
            feature_flag_name=feature_flag_name, user=user
        )

        serializer = FeatureFlagStatusResponseSerializer({
            "enabled": enabled,
            "feature_flag_name": feature_flag_name,
            "reason": reason,
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

        owned_orgs = Organization.objects.filter(owner=user)
        member_orgs = Organization.objects.none()
        if hasattr(user, "profile") and user.profile.organization:
            member_orgs = Organization.objects.filter(id=user.profile.organization.id)
        user_organizations = list((owned_orgs | member_orgs).distinct())

        # Owners start with all registry flags True; members start empty. Both then merge
        # user assignments, role capabilities, and org_only assignments (matches per-flag checks).
        if owned_orgs.exists():
            all_flags = {name: True for name in KNOWN_FEATURE_FLAGS}
        else:
            all_flags = {}

        user_assignments = FeatureFlagAssignment.objects.filter(
            user=user, organization__isnull=True
        ).select_related("feature_flag")
        for assignment in user_assignments:
            all_flags[assignment.feature_flag.name] = assignment.enabled

        for org in user_organizations:
            for flag_name in FeatureFlagService.get_user_role_capabilities(user, org):
                if flag_name not in all_flags:
                    all_flags[flag_name] = True

        org_only_names = set(
            FeatureFlag.objects.filter(organization_only=True)
            .values_list("name", flat=True)
        )
        for org in user_organizations:
            org_flags = FeatureFlagService.get_organization_feature_flags(org)
            for flag_name, enabled in org_flags.items():
                if flag_name in org_only_names and flag_name not in all_flags:
                    all_flags[flag_name] = enabled

        serializer = TeamFeatureFlagsResponseSerializer({
            "feature_flags": all_flags,
        })
        response_data = serializer.data
        cache.set(cache_key, response_data, timeout=self.CACHE_TIMEOUT)
        return JsonResponse(response_data, status=status.HTTP_200_OK)


def _organization_has_active_subscription(organization) -> bool:
    subscription = (
        Subscription.objects.filter(organization=organization)
        .order_by("-created_at")
        .first()
    )
    return bool(subscription and subscription.is_active())


def _sync_tenant_favicon(organization: Organization) -> None:
    tenant = get_tenant_for_organization(organization)
    if not tenant:
        return
    if organization.logo:
        regenerate_tenant_favicon_from_logo(organization)
    else:
        clear_tenant_favicon(tenant)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class OrganizationTenantView(View):
    """Read or update portal branding for an organization."""

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
                {"error": "You do not have permission to manage this organization"},
                status=status.HTTP_403_FORBIDDEN,
            )

        tenant = get_tenant_for_organization(organization)
        if not tenant:
            return JsonResponse(
                {
                    "subdomain": None,
                    "app_name": "",
                    "theme": {},
                    "hide_powered_by": False,
                    "favicon_url": organization.logo.url if organization.logo else None,
                    "logo_url": organization.logo.url if organization.logo else None,
                },
                status=status.HTTP_200_OK,
            )

        return JsonResponse(
            serialize_tenant_for_manage(tenant, request),
            status=status.HTTP_200_OK,
        )

    def put(self, request, organization_id):
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return JsonResponse(
                {"error": "Organization not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not _can_manage_organization(request.user, organization):
            return JsonResponse(
                {"error": "You do not have permission to manage this organization"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not _organization_has_active_subscription(organization):
            return JsonResponse(
                {"error": "An active subscription is required to customize portal branding"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            data = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return JsonResponse(
                {"error": "Invalid JSON"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tenant = get_or_create_tenant(organization)

        if "app_name" in data:
            tenant.app_name = (data.get("app_name") or "").strip()

        if "hide_powered_by" in data:
            tenant.hide_powered_by = bool(data.get("hide_powered_by"))

        if "theme" in data:
            try:
                tenant.theme = validate_tenant_theme(data.get("theme") or {})
            except ValueError as exc:
                return JsonResponse(
                    {"error": str(exc)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        tenant.save()
        return JsonResponse(
            serialize_tenant_for_manage(tenant, request),
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class OrganizationTenantSubdomainView(View):
    """Claim or release an organization's tenant subdomain."""

    def post(self, request, organization_id):
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return JsonResponse(
                {"error": "Organization not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not _can_manage_organization(request.user, organization):
            return JsonResponse(
                {"error": "You do not have permission to manage this organization"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not _organization_has_active_subscription(organization):
            return JsonResponse(
                {"error": "An active subscription is required to claim a subdomain"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            data = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return JsonResponse(
                {"error": "Invalid JSON"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_subdomain = data.get("subdomain", "")
        try:
            subdomain = validate_subdomain(raw_subdomain)
        except ValidationError as exc:
            return JsonResponse(
                {"error": exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tenant = get_or_create_tenant(organization)
        existing = (
            OrganizationTenant.objects.filter(subdomain=subdomain)
            .exclude(pk=tenant.pk)
            .exists()
        )
        if existing:
            return JsonResponse(
                {"error": "This subdomain is already taken"},
                status=status.HTTP_409_CONFLICT,
            )

        tenant.subdomain = subdomain
        try:
            tenant.save(update_fields=["subdomain", "updated_at"])
        except IntegrityError:
            return JsonResponse(
                {"error": "This subdomain is already taken"},
                status=status.HTTP_409_CONFLICT,
            )

        _sync_tenant_favicon(organization)
        return JsonResponse(
            serialize_tenant_for_manage(tenant, request),
            status=status.HTTP_200_OK,
        )

    def delete(self, request, organization_id):
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return JsonResponse(
                {"error": "Organization not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not _can_manage_organization(request.user, organization):
            return JsonResponse(
                {"error": "You do not have permission to manage this organization"},
                status=status.HTTP_403_FORBIDDEN,
            )

        tenant = get_tenant_for_organization(organization)
        if not tenant or not tenant.subdomain:
            return JsonResponse(
                {"error": "No subdomain is currently claimed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tenant.subdomain = None
        tenant.save(update_fields=["subdomain", "updated_at"])
        return JsonResponse(
            serialize_tenant_for_manage(tenant, request),
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class TenantConfigView(View):
    """Public tenant branding resolved from Host header or authenticated user's org."""

    def get(self, request):
        subdomain = extract_subdomain(request.get_host())
        if subdomain:
            try:
                tenant = OrganizationTenant.objects.select_related("organization").get(
                    subdomain=subdomain
                )
            except OrganizationTenant.DoesNotExist:
                return JsonResponse({}, status=status.HTTP_200_OK)

            return JsonResponse(
                build_public_tenant_config(tenant, request),
                status=status.HTTP_200_OK,
            )

        user = user_from_optional_auth_header(request)
        if user:
            organization = get_user_organization(user)
            if organization:
                tenant = get_tenant_for_organization(organization)
                if tenant:
                    return JsonResponse(
                        build_public_tenant_config(tenant, request),
                        status=status.HTTP_200_OK,
                    )

        return JsonResponse({}, status=status.HTTP_200_OK)
