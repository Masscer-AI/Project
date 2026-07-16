"""OAuth models for MCP authorization server."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from api.mcp_oauth.crypto import generate_client_id, generate_token, hash_secret


class OAuthClient(models.Model):
    REGISTRATION_MANUAL = "manual"
    REGISTRATION_DCR = "dcr"
    REGISTRATION_CIMD = "cimd"
    REGISTRATION_SOURCE_CHOICES = [
        (REGISTRATION_MANUAL, "Manual"),
        (REGISTRATION_DCR, "Dynamic Client Registration"),
        (REGISTRATION_CIMD, "Client ID Metadata Document"),
    ]

    AUTH_NONE = "none"
    AUTH_SECRET_BASIC = "client_secret_basic"
    AUTH_SECRET_POST = "client_secret_post"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client_id = models.CharField(max_length=512, unique=True, db_index=True)
    client_secret_hash = models.CharField(max_length=64, blank=True, default="")
    client_name = models.CharField(max_length=255)
    redirect_uris = models.JSONField(default=list, blank=True)
    token_endpoint_auth_method = models.CharField(
        max_length=32,
        default=AUTH_NONE,
    )
    grant_types = models.JSONField(
        default=list,
        blank=True,
        help_text="Allowed grant types, e.g. authorization_code, refresh_token",
    )
    scope = models.CharField(max_length=255, blank=True, default="mcp offline_access")
    registration_source = models.CharField(
        max_length=16,
        choices=REGISTRATION_SOURCE_CHOICES,
        default=REGISTRATION_MANUAL,
    )
    cimd_url = models.URLField(max_length=512, blank=True, default="")
    owner_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="oauth_clients",
    )
    organization = models.ForeignKey(
        "authenticate.Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="oauth_clients",
    )
    disabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"OAuthClient({self.client_name}, {self.client_id[:32]})"

    @classmethod
    def create_manual(
        cls,
        *,
        client_name: str,
        redirect_uris: list[str],
        owner_user,
        organization=None,
        confidential: bool = True,
    ) -> tuple["OAuthClient", str | None]:
        secret = generate_token(32) if confidential else None
        client = cls.objects.create(
            client_id=generate_client_id(),
            client_secret_hash=hash_secret(secret) if secret else "",
            client_name=client_name,
            redirect_uris=redirect_uris,
            token_endpoint_auth_method=(
                cls.AUTH_SECRET_POST if confidential else cls.AUTH_NONE
            ),
            grant_types=["authorization_code", "refresh_token"],
            registration_source=cls.REGISTRATION_MANUAL,
            owner_user=owner_user,
            organization=organization,
        )
        return client, secret


class OAuthAuthorizationRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(
        OAuthClient,
        on_delete=models.CASCADE,
        related_name="authorization_requests",
    )
    redirect_uri = models.TextField()
    state = models.CharField(max_length=512, blank=True, default="")
    code_challenge = models.CharField(max_length=128)
    code_challenge_method = models.CharField(max_length=16, default="S256")
    scope = models.CharField(max_length=255, blank=True, default="")
    resource = models.TextField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="oauth_authorization_requests",
    )
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at


class OAuthAuthorizationCode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code_hash = models.CharField(max_length=64, unique=True, db_index=True)
    client = models.ForeignKey(
        OAuthClient,
        on_delete=models.CASCADE,
        related_name="authorization_codes",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="oauth_authorization_codes",
    )
    mcp_client = models.ForeignKey(
        "ai_layers.MCPClient",
        on_delete=models.CASCADE,
        related_name="oauth_authorization_codes",
    )
    redirect_uri = models.TextField()
    code_challenge = models.CharField(max_length=128)
    scope = models.CharField(max_length=255, blank=True, default="")
    resource = models.TextField()
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def is_consumed(self) -> bool:
        return self.consumed_at is not None


class OAuthAccessToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    client = models.ForeignKey(
        OAuthClient,
        on_delete=models.CASCADE,
        related_name="access_tokens",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="oauth_access_tokens",
    )
    mcp_client = models.ForeignKey(
        "ai_layers.MCPClient",
        on_delete=models.CASCADE,
        related_name="oauth_access_tokens",
    )
    scope = models.CharField(max_length=255, blank=True, default="")
    resource = models.TextField()
    expires_at = models.DateTimeField()
    revoked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def is_active(self) -> bool:
        return not self.revoked and not self.is_expired()


class OAuthRefreshToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    family_id = models.UUIDField(db_index=True)
    client = models.ForeignKey(
        OAuthClient,
        on_delete=models.CASCADE,
        related_name="refresh_tokens",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="oauth_refresh_tokens",
    )
    mcp_client = models.ForeignKey(
        "ai_layers.MCPClient",
        on_delete=models.CASCADE,
        related_name="oauth_refresh_tokens",
    )
    scope = models.CharField(max_length=255, blank=True, default="")
    resource = models.TextField()
    expires_at = models.DateTimeField()
    rotated_at = models.DateTimeField(null=True, blank=True)
    revoked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def is_active(self) -> bool:
        return not self.revoked and not self.is_expired() and self.rotated_at is None
