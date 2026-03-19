"""
Models for the Cloudbeds integration.

CloudbedsCredential stores OAuth tokens per organization so that agent tools
can make authenticated Cloudbeds API calls on behalf of each property.
"""

from django.db import models


class CloudbedsCredential(models.Model):
    """
    OAuth 2.0 credentials for a single Cloudbeds property, scoped to an
    Organization. Each organization can have at most one active connection.
    """

    organization = models.OneToOneField(
        "authenticate.Organization",
        on_delete=models.CASCADE,
        related_name="cloudbeds_credential",
    )

    # OAuth tokens
    access_token = models.TextField(help_text="Cloudbeds OAuth access token.")
    refresh_token = models.TextField(
        blank=True,
        default="",
        help_text="Cloudbeds OAuth refresh token (used to obtain a new access token).",
    )
    token_type = models.CharField(max_length=50, default="Bearer")
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="UTC datetime when the access_token expires. Null = non-expiring.",
    )

    # Property metadata (cached at connect time)
    property_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Cloudbeds property ID associated with this token.",
    )
    property_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Display name of the connected Cloudbeds property.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cloudbeds Credential"
        verbose_name_plural = "Cloudbeds Credentials"

    def __str__(self):
        return f"CloudbedsCredential(org={self.organization_id}, property={self.property_name or self.property_id})"

    @property
    def is_expired(self) -> bool:
        """True if the access token has expired (with a 60-second buffer)."""
        if not self.expires_at:
            return False
        from django.utils import timezone
        return self.expires_at <= timezone.now() + timezone.timedelta(seconds=60)
