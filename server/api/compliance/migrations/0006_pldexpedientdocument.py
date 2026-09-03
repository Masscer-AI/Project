import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import api.compliance.models


class Migration(migrations.Migration):

    dependencies = [
        ("compliance", "0005_rename_compliance__organiz_pldinv_idx_compliance__organiz_f4c259_idx_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PLDExpedientDocument",
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
                ("slot_key", models.CharField(max_length=64)),
                ("document_kind", models.CharField(max_length=64)),
                (
                    "file",
                    models.FileField(
                        upload_to=api.compliance.models.pld_expedient_document_upload_to,
                    ),
                ),
                (
                    "original_filename",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "content_type",
                    models.CharField(blank=True, default="", max_length=128),
                ),
                ("file_size", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "expedient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to="compliance.pldexpedient",
                    ),
                ),
                (
                    "uploaded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="pld_expedient_documents",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "PLD expedient document",
                "verbose_name_plural": "PLD expedient documents",
                "ordering": ["slot_key"],
            },
        ),
        migrations.AddIndex(
            model_name="pldexpedientdocument",
            index=models.Index(
                fields=["expedient", "document_kind"],
                name="compliance__expedie_doc_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="pldexpedientdocument",
            constraint=models.UniqueConstraint(
                fields=("expedient", "slot_key"),
                name="unique_pld_document_slot_per_expedient",
            ),
        ),
    ]
