"""
Models for third-party integrations (Google Drive, future providers).

Each Integration row belongs to EITHER a user OR an organization (exactly one).
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .schemas import validate_provider_metadata


class IntegrationProvider(models.TextChoices):
    GOOGLE_DRIVE = "google_drive", "Google Drive"


class IntegrationStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    REVOKED = "revoked", "Revoked"


class Integration(models.Model):
    """
    OAuth credentials for a third-party provider, scoped to a user OR an organization.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="integrations",
    )
    organization = models.ForeignKey(
        "authenticate.Organization",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="integrations",
    )
    provider = models.CharField(
        max_length=64,
        choices=IntegrationProvider.choices,
    )
    access_token = models.TextField(help_text="OAuth access token.")
    refresh_token = models.TextField(
        blank=True,
        default="",
        help_text="OAuth refresh token (used to obtain a new access token).",
    )
    token_type = models.CharField(max_length=50, default="Bearer")
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="UTC datetime when the access_token expires. Null = non-expiring.",
    )
    scopes = models.TextField(
        blank=True,
        default="",
        help_text="Space-separated OAuth scopes granted at connect time.",
    )
    account_email = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Email of the connected third-party account.",
    )
    account_label = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Display label for the connected account.",
    )
    metadata = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=IntegrationStatus.choices,
        default=IntegrationStatus.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Integration"
        verbose_name_plural = "Integrations"
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(user__isnull=False, organization__isnull=True)
                    | Q(user__isnull=True, organization__isnull=False)
                ),
                name="integration_exactly_one_owner",
            ),
            models.UniqueConstraint(
                fields=["user", "provider"],
                condition=Q(user__isnull=False),
                name="integration_unique_user_provider",
            ),
            models.UniqueConstraint(
                fields=["organization", "provider"],
                condition=Q(organization__isnull=False),
                name="integration_unique_organization_provider",
            ),
        ]

    def __str__(self) -> str:
        owner = self.owner_label or "unknown"
        return f"Integration({self.provider}, owner={owner})"

    @property
    def owner_type(self) -> str:
        if self.user_id and not self.organization_id:
            return "user"
        if self.organization_id and not self.user_id:
            return "organization"
        return "invalid"

    @property
    def owner_label(self) -> str:
        if self.user_id:
            return getattr(self.user, "email", None) or f"user:{self.user_id}"
        if self.organization_id:
            return getattr(self.organization, "name", None) or f"org:{self.organization_id}"
        return ""

    @property
    def is_expired(self) -> bool:
        """True if the access token has expired (with a 60-second buffer)."""
        if not self.expires_at:
            return False
        return self.expires_at <= timezone.now() + timezone.timedelta(seconds=60)

    def clean(self) -> None:
        has_user = self.user_id is not None
        has_org = self.organization_id is not None
        if has_user == has_org:
            raise ValidationError(
                "Exactly one of user or organization must be set (not both, not neither)."
            )
        try:
            self.metadata = validate_provider_metadata(self.provider, self.metadata)
        except Exception as exc:
            raise ValidationError({"metadata": str(exc)}) from exc

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)
