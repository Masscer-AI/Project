import uuid
import os
from django.db import models
import rest_framework.authtoken.models
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta
from django.core.exceptions import MultipleObjectsReturned, ValidationError
from django.db.models import Q
from model_utils.models import TimeStampedModel
import pytz
from PIL import Image


LOGIN_TOKEN_LIFETIME = timezone.timedelta(days=1)
TEMPORAL_TOKEN_LIFETIME = timezone.timedelta(days=7)
TOKEN_TYPE = ["one_time", "temporal", "permanent", "login"]


class InvalidTokenType(Exception):
    pass


class TryToGetOrCreateAOneTimeToken(Exception):
    pass


class BadArguments(Exception):
    pass


class UserProxy(User):
    class Meta:
        proxy = True


class Token(rest_framework.authtoken.models.Token):
    """
    create multi token per user - override default rest_framework Token class
    replace model one-to-one relationship with foreign key
    """

    key = models.CharField(max_length=40, db_index=True, unique=True, blank=True)
    # Foreign key relationship to user for many-to-one relationship
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="auth_token",
        on_delete=models.CASCADE,
        verbose_name="User",
    )
    token_type = models.CharField(
        max_length=64,
        default="temporal",
        help_text=(
            "The other choice is permanent or one_time, it does not set a expires_at to the token, login has a duration of 1 day, temporal has a duration of 10 minutes"
        ),
    )
    expires_at = models.DateTimeField(default=None, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    def save(self, *args, **kwargs):
        without_expire_at = not self.expires_at
        if without_expire_at and self.token_type == "login":
            utc_now = timezone.now()
            self.expires_at = utc_now + LOGIN_TOKEN_LIFETIME

        if without_expire_at and self.token_type == "temporal":
            utc_now = timezone.now()
            self.expires_at = utc_now + TEMPORAL_TOKEN_LIFETIME

        if self.token_type == "one_time" or self.token_type == "permanent":
            self.expires_at = None

        if not self.key:
            self.key = self.generate_key()

        super().save(*args, **kwargs)

    @staticmethod
    def delete_expired_tokens(utc_now: datetime = timezone.now()) -> None:
        """Delete expired tokens"""
        utc_now = timezone.now()
        Token.objects.filter(expires_at__lt=utc_now).delete()

    @classmethod
    def get_or_create(cls, user, token_type: str, **kwargs):
        utc_now = timezone.now()
        kwargs["token_type"] = token_type

        cls.delete_expired_tokens(utc_now)

        if token_type not in TOKEN_TYPE:
            raise InvalidTokenType(
                f'Invalid token_type, correct values are {", ".join(TOKEN_TYPE)}'
            )

        has_hours_length = "hours_length" in kwargs
        has_expires_at = "expires_at" in kwargs

        if (token_type == "one_time" or token_type == "permanent") and (
            has_hours_length or has_expires_at
        ):
            raise BadArguments(
                f"You can't provide token_type='{token_type}' and "
                "has_hours_length or has_expires_at together"
            )

        if has_hours_length and has_expires_at:
            raise BadArguments(
                "You can't provide hours_length and expires_at argument together"
            )

        if has_hours_length:
            kwargs["expires_at"] = utc_now + timezone.timedelta(
                hours=kwargs["hours_length"]
            )
            del kwargs["hours_length"]

        token = None
        created = False

        try:
            if token_type == "one_time":
                raise TryToGetOrCreateAOneTimeToken()

            token, created = Token.objects.get_or_create(user=user, **kwargs)

        except MultipleObjectsReturned:
            token = Token.objects.filter(user=user, **kwargs).first()

        except TryToGetOrCreateAOneTimeToken:
            created = True
            token = Token.objects.create(user=user, **kwargs)

        return token, created

    @classmethod
    def get_valid(cls, token: str):
        utc_now = timezone.now()
        cls.delete_expired_tokens(utc_now)

        # find among any non-expired token
        return (
            Token.objects.filter(key=token)
            .filter(Q(expires_at__gt=utc_now) | Q(expires_at__isnull=True))
            .first()
        )

    @classmethod
    def validate_and_destroy(cls, user: User, hash: str) -> None:
        token = Token.objects.filter(key=hash, user=user, token_type="one_time").first()
        if not token:
            raise Exception("Token not found")

        token.delete()

    class Meta:
        # ensure user and name are unique
        unique_together = (("user", "key"),)

    def generate_key(self):
        return uuid.uuid4().hex


class PublishableToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.CharField(max_length=255, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.IntegerField(null=True, blank=True)
    duration_hours = models.IntegerField(null=True, blank=True)
    duration_days = models.IntegerField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.expires_at and (
            self.duration_minutes or self.duration_hours or self.duration_days
        ):
            duration = timedelta(
                minutes=self.duration_minutes or 0,
                hours=self.duration_hours or 0,
                days=self.duration_days or 0,
            )
            self.expires_at = timezone.now() + duration

        if not self.token:
            self.token = uuid.uuid4().hex

        super().save(*args, **kwargs)

    def __str__(self):
        return self.token

    @classmethod
    def get_valid(cls, token: str):
        utc_now = timezone.now()
        cls.objects.filter(expires_at__lt=utc_now).delete()
        return (
            cls.objects.filter(token=token)
            .filter(Q(expires_at__gt=utc_now) | Q(expires_at__isnull=True))
            .first()
        )


def organization_logo_upload_path(instance, filename):
    """Genera la ruta para almacenar el logo de la organización"""
    ext = filename.split('.')[-1]
    # Nombre único: organization_id.ext
    filename = f"{instance.id}.{ext}"
    return os.path.join('organizations', 'logos', filename)


class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    # slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(null=True, blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    timezone = models.CharField(
        max_length=50,
        default='UTC',
        choices=[(tz, tz) for tz in pytz.all_timezones],
        help_text="Zona horaria de la organización para mostrar timestamps"
    )
    logo = models.ImageField(
        upload_to=organization_logo_upload_path,
        null=True,
        blank=True,
        help_text="Logo de la organización (recomendado: 500x500px, formato PNG/JPG/SVG)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
    def get_timezone(self):
        """Retorna el objeto timezone de pytz"""
        return pytz.timezone(self.timezone)
    
    def save(self, *args, **kwargs):
        """Guarda la organización. La gestión del logo se hace en la vista."""
        super().save(*args, **kwargs)


class CredentialsManager(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    openai_api_key = models.CharField(max_length=255, null=True, blank=True)
    brave_api_key = models.CharField(max_length=255, null=True, blank=True)
    anthropic_api_key = models.CharField(max_length=255, null=True, blank=True)
    pexels_api_key = models.CharField(max_length=255, null=True, blank=True)
    elevenlabs_api_key = models.CharField(max_length=255, null=True, blank=True)
    heygen_api_key = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"<CredentialsManager for {self.organization.name}>"



class UserProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    name = models.CharField(max_length=255, null=True, blank=True, default="")
    avatar_url = models.TextField(null=True, blank=True, default="")
    bio = models.TextField(null=True, blank=True, default="")
    sex = models.CharField(max_length=255, null=True, blank=True, default="")
    age = models.IntegerField(null=True, blank=True, default=0)
    birthday = models.DateField(null=True, blank=True, default=None)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members',
        help_text="Organización a la que pertenece el usuario"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"USER_PROFILE(user={self.user.username or self.user.email})"

    def get_as_text(self):
        is_empty = True
        text = "This is information about the user:\n<USER_PROFILE>\n"
        if self.name:
            text += f"name={self.name}\n"
            is_empty = False
        if self.bio:
            text += f"bio={self.bio}\n"
            is_empty = False
        if self.sex:
            text += f"sex={self.sex}\n"
            is_empty = False
        if self.age:
            text += f"age={self.age}\n"
            is_empty = False
        if self.birthday:
            text += f"birthday={self.birthday}\n"
            is_empty = False
        if is_empty:
            return ""
        text += "</USER_PROFILE>\n"
        return text


class FeatureFlag(TimeStampedModel):
    name = models.CharField(max_length=255, unique=True)
    organization_only = models.BooleanField(
        default=False,
        help_text="If True, this flag can only be assigned at the organization level (not to users or as role capabilities).",
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Feature Flag"
        verbose_name_plural = "Feature Flags"


class FeatureFlagAssignment(TimeStampedModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="feature_flag_assignments",
        null=True,
        blank=True,
        help_text="Organization for organization-level feature flags. Leave blank for user-level flags.",
    )
    feature_flag = models.ForeignKey(
        FeatureFlag, on_delete=models.CASCADE, related_name="assignments"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="feature_flag_assignments",
        null=True,
        blank=True,
        help_text="User for user-level feature flags. Leave blank for organization-level flags.",
    )
    enabled = models.BooleanField(default=False)

    def clean(self):
        """Validate that either organization or user is set, but not both or neither."""
        super().clean()

        # Must have exactly one of organization or user
        if not self.organization_id and not self.user_id:
            raise ValidationError(
                "Must specify either an organization (for organization-level flag) or a user (for user-level flag)."
            )

        if self.organization_id and self.user_id:
            raise ValidationError(
                "Cannot specify both organization and user. Choose either organization-level or user-level flag."
            )

        # Organization-only flags cannot be assigned to individual users
        if self.user_id and self.feature_flag_id:
            try:
                if self.feature_flag.organization_only:
                    raise ValidationError(
                        f"The feature flag '{self.feature_flag.name}' is organization-only and cannot be assigned to individual users."
                    )
            except FeatureFlag.DoesNotExist:
                pass

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        try:
            if self.user_id:
                user_email = self.user.email if self.user else f"User #{self.user_id}"
                flag_name = self.feature_flag.name
                return f"{user_email} - {flag_name} ({'enabled' if self.enabled else 'disabled'})"

            org_name = self.organization.name if self.organization_id and self.organization else "Unknown Organization"
            flag_name = self.feature_flag.name
            return f"{org_name} - {flag_name} ({'enabled' if self.enabled else 'disabled'})"
        except:
            return f"FeatureFlagAssignment #{self.pk or '(new)'}"

    class Meta:
        verbose_name = "Feature Flag Assignment"
        verbose_name_plural = "Feature Flag Assignments"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "feature_flag"],
                condition=models.Q(organization__isnull=False, user__isnull=True),
                name="unique_organization_feature_flag",
            ),
            models.UniqueConstraint(
                fields=["user", "feature_flag"],
                condition=models.Q(user__isnull=False, organization__isnull=True),
                name="unique_user_feature_flag",
            ),
        ]

class Role(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="roles",
        help_text="Organization this role belongs to"
    )
    name = models.CharField(
        max_length=50,
        help_text="Name of the role"
    )
    description = models.TextField(
        null=True,
        blank=True,
        help_text="Description of the role"
    )
    enabled = models.BooleanField(
        default=True,
        help_text="Whether this role exists under the organization or not"
    )
    capabilities = models.JSONField(
        default=list,
        blank=True,
        help_text="List of feature flag slugs that this role will have enabled"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Role"
        verbose_name_plural = "Roles"
        unique_together = [("organization", "name")]

    def __str__(self):
        return f"{self.name} ({self.organization.name})"


class RoleAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="role_assignments",
        help_text="User to whom the role is assigned"
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="role_assignments",
        help_text="Organization this assignment belongs to"
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="assignments",
        help_text="Role being assigned"
    )
    from_date = models.DateField(
        help_text="Date from which the user has this role"
    )
    to_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date until which the user has this role. Empty if the role is active or has no end date"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Role Assignment"
        verbose_name_plural = "Role Assignments"
        indexes = [
            models.Index(fields=["user", "organization"]),
            models.Index(fields=["from_date", "to_date"]),
        ]

    def __str__(self):
        status = "Active" if not self.to_date or self.to_date >= timezone.now().date() else "Inactive"
        return f"{self.user.email} - {self.role.name} ({self.organization.name}) - {status}"

    def is_active(self):
        """Check if the role assignment is currently active"""
        today = timezone.now().date()
        return (
            self.from_date <= today and
            (self.to_date is None or self.to_date >= today)
        )