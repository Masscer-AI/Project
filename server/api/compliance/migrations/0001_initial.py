import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("authenticate", "0028_organizationinvite_role"),
        ("messaging", "0036_messageattachment_visibility_db_default"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ComplianceFolio",
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
                            ("open", "Open"),
                            ("awaiting_documents", "Awaiting documents"),
                            ("in_review", "In review"),
                            ("needs_correction", "Needs correction"),
                            ("pending_signature", "Pending signature"),
                            ("cleared", "Cleared"),
                            ("rejected", "Rejected"),
                            ("archived", "Archived"),
                        ],
                        db_index=True,
                        default="open",
                        max_length=32,
                    ),
                ),
                (
                    "notes",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Working summary for the compliance agent (replaceable).",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="compliance_folios",
                        to="authenticate.organization",
                    ),
                ),
                (
                    "subject_user",
                    models.ForeignKey(
                        help_text="Invited counterparty this expediente belongs to.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="compliance_folios",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Compliance folio",
                "verbose_name_plural": "Compliance folios",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="FolioDocument",
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
                    "document_kind",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Checklist type (e.g. ine, constancia_fiscal). Empty until classified.",
                        max_length=64,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("uploaded", "Uploaded"),
                            ("validated", "Validated"),
                            ("rejected", "Rejected"),
                            ("expired", "Expired"),
                            ("superseded", "Superseded"),
                        ],
                        db_index=True,
                        default="uploaded",
                        max_length=32,
                    ),
                ),
                (
                    "notes",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Why rejected, what is missing, validation notes.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "attachment",
                    models.OneToOneField(
                        help_text="Chat file that holds the uploaded bytes.",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="folio_document",
                        to="messaging.messageattachment",
                    ),
                ),
                (
                    "folio",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to="compliance.compliancefolio",
                    ),
                ),
            ],
            options={
                "verbose_name": "Folio document",
                "verbose_name_plural": "Folio documents",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="FolioEvent",
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
                    "event_type",
                    models.CharField(
                        choices=[
                            ("folio_created", "Folio created"),
                            ("folio_status_changed", "Folio status changed"),
                            ("document_uploaded", "Document uploaded"),
                            ("document_updated", "Document updated"),
                            ("notes_updated", "Notes updated"),
                        ],
                        max_length=32,
                    ),
                ),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="compliance_folio_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "folio",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to="compliance.compliancefolio",
                    ),
                ),
                (
                    "folio_document",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="events",
                        to="compliance.foliodocument",
                    ),
                ),
            ],
            options={
                "verbose_name": "Folio event",
                "verbose_name_plural": "Folio events",
                "ordering": ["created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="compliancefolio",
            index=models.Index(
                fields=["organization", "status"],
                name="compliance__organiz_folio_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="compliancefolio",
            constraint=models.UniqueConstraint(
                fields=("organization", "subject_user"),
                name="unique_compliance_folio_per_org_user",
            ),
        ),
        migrations.AddIndex(
            model_name="foliodocument",
            index=models.Index(
                fields=["folio", "status"],
                name="compliance__folio_d_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="folioevent",
            index=models.Index(
                fields=["folio", "event_type"],
                name="compliance__folio_e_type_idx",
            ),
        ),
    ]
