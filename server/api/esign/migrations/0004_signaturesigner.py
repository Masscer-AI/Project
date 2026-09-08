import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("esign", "0003_signaturerequest_source_file_optional"),
    ]

    operations = [
        migrations.CreateModel(
            name="SignatureSigner",
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
                    "role",
                    models.CharField(
                        choices=[
                            ("counterparty", "Contraparte"),
                            ("representative", "Representante legal"),
                            ("controller", "Beneficiario controlador"),
                        ],
                        default="counterparty",
                        max_length=32,
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("email", models.EmailField(max_length=254)),
                ("rfc", models.CharField(blank=True, default="", max_length=13)),
                (
                    "provider_widget_id",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pendiente"),
                            ("signed", "Firmado"),
                            ("rejected", "Rechazado"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("signed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "signature_request",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="signers",
                        to="esign.signaturerequest",
                    ),
                ),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.AddConstraint(
            model_name="signaturesigner",
            constraint=models.UniqueConstraint(
                fields=("signature_request", "email"),
                name="unique_signer_email_per_signature_request",
            ),
        ),
    ]
