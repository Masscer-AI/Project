# Generated manually — OrganizationInvite for email-based member onboarding.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authenticate", "0020_remove_credentialsmanager_brave_api_key"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrganizationInvite",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("email", models.EmailField(max_length=254)),
                ("name", models.CharField(blank=True, default="", max_length=255)),
                ("bio", models.TextField(blank=True, default="")),
                ("profile_expires_at", models.DateTimeField(blank=True, null=True)),
                ("token_hash", models.CharField(max_length=64, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("accepted", "Accepted"),
                            ("cancelled", "Cancelled"),
                            ("expired", "Expired"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("invite_expires_at", models.DateTimeField()),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "accepted_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="accepted_organization_invites",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "invited_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="organization_invites_sent",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invites",
                        to="authenticate.organization",
                    ),
                ),
            ],
            options={
                "verbose_name": "Organization invite",
                "verbose_name_plural": "Organization invites",
            },
        ),
        migrations.AddIndex(
            model_name="organizationinvite",
            index=models.Index(
                fields=["organization", "status"],
                name="authentica_organiz_a772fc_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="organizationinvite",
            constraint=models.UniqueConstraint(
                condition=models.Q(status="pending"),
                fields=("organization", "email"),
                name="unique_pending_org_invite_email",
            ),
        ),
    ]
