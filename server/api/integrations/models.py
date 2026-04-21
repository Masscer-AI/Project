"""
Third-party integrations (non–Cloudbeds). Cloudbeds stays in api.cloudbeds.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class GoogleDriveConnection(models.Model):
    """
    One Google account linked to one Masscer user for Drive API (e.g. attach
    files from Drive, future uploads). Separate from login-only Google OAuth.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REVOKED = "revoked", "Revoked"
        NEEDS_REAUTH = "needs_reauth", "Needs re-authentication"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="google_drive_connection",
    )
    google_subject = models.CharField(
        max_length=255,
        db_index=True,
        help_text="OpenID Connect 'sub' for the Google account (stable id).",
    )
    google_email = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Google account email for display.",
    )

    access_token = models.TextField(help_text="OAuth 2.0 access token (short-lived).")
    refresh_token = models.TextField(
        blank=True,
        default="",
        help_text="OAuth 2.0 refresh token; empty if not issued or stripped on re-auth.",
    )
    token_type = models.CharField(max_length=32, default="Bearer")
    access_token_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="UTC expiry of access_token; refresh before Drive API calls when set.",
    )
    scopes = models.TextField(
        blank=True,
        default="",
        help_text="Granted OAuth scopes (e.g. space-separated), for UI and permission checks.",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    last_token_error = models.TextField(
        blank=True,
        default="",
        help_text="Last token refresh or auth error message (truncated in app code if needed).",
    )

    default_upload_folder_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Drive file id of the folder used as default for uploads.",
    )
    default_upload_folder_name = models.CharField(
        max_length=512,
        blank=True,
        default="",
        help_text="Cached display name of default_upload_folder_id.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Google Drive connection"
        verbose_name_plural = "Google Drive connections"

    def __str__(self) -> str:
        return (
            f"GoogleDriveConnection(user_id={self.user_id}, "
            f"google_email={self.google_email or self.google_subject})"
        )
