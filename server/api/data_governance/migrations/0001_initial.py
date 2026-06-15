# Generated manually for data_governance

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("authenticate", "0023_organizationmanagementproxy"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OrganizationDataPolicy",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "deleted_conversation_retention_days",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text="Days after soft-delete before hard deletion. null = keep forever.",
                        null=True,
                    ),
                ),
                (
                    "attachment_retention_days",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text="Days to keep file attachments. null = keep forever.",
                        null=True,
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="data_policy",
                        to="authenticate.organization",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="data_policy_updates",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Organization data policy",
                "verbose_name_plural": "Organization data policies",
            },
        ),
        migrations.CreateModel(
            name="DataPurgeLog",
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
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("deleted_conversations", "Deleted conversations"),
                            ("attachments", "Attachments"),
                        ],
                        max_length=32,
                    ),
                ),
                ("count", models.PositiveIntegerField(default=0)),
                ("run_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="data_purge_logs",
                        to="authenticate.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["-run_at"],
            },
        ),
        migrations.CreateModel(
            name="DataExportJob",
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
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("processing", "Processing"),
                            ("ready", "Ready"),
                            ("failed", "Failed"),
                            ("expired", "Expired"),
                            ("downloaded", "Downloaded"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                (
                    "notify_via",
                    models.CharField(
                        choices=[
                            ("app", "App"),
                            ("email", "Email"),
                            ("both", "Both"),
                        ],
                        default="both",
                        max_length=10,
                    ),
                ),
                ("manifest", models.JSONField(default=dict)),
                (
                    "file",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to="data_exports/%Y/%m/",
                    ),
                ),
                ("file_size_bytes", models.BigIntegerField(blank=True, null=True)),
                ("download_count", models.PositiveIntegerField(default=0)),
                ("downloaded_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="data_exports",
                        to="authenticate.organization",
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="data_export_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
