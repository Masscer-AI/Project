import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compliance", "0003_rename_compliance__organiz_folio_idx_compliance__organiz_97edcb_idx_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="pldentity",
            name="email",
            field=models.EmailField(
                blank=True,
                default="",
                help_text="Contact email for expediente invitations. Empty for the org self-entity.",
                max_length=254,
            ),
        ),
        migrations.CreateModel(
            name="PLDInvite",
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
                        related_name="accepted_pld_invites",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "entity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invites",
                        to="compliance.pldentity",
                    ),
                ),
                (
                    "invited_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pld_invites_sent",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pld_invites",
                        to="authenticate.organization",
                    ),
                ),
            ],
            options={
                "verbose_name": "PLD invite",
                "verbose_name_plural": "PLD invites",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="pldinvite",
            index=models.Index(
                fields=["organization", "status"],
                name="compliance__organiz_pldinv_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="pldinvite",
            index=models.Index(
                fields=["email", "status"],
                name="compliance__email_pldinv_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="pldinvite",
            constraint=models.UniqueConstraint(
                condition=models.Q(status="pending"),
                fields=["entity"],
                name="unique_pending_pld_invite_per_entity",
            ),
        ),
    ]
