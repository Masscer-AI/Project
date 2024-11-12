import uuid
from django.db import models
import rest_framework.authtoken.models
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta
from django.core.exceptions import MultipleObjectsReturned
from django.db.models import Q


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

    key = models.CharField(max_length=40, db_index=True, unique=True)
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


class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    # slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(null=True, blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class OrganizationMember(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



class CredentialsManager(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    openai_api_key = models.CharField(max_length=255,null=True, blank=True)
    brave_api_key = models.CharField(max_length=255, null=True, blank=True)
    anthropic_api_key = models.CharField(max_length=255, null=True, blank=True)
    pexels_api_key = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name