import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authenticate", "0029_organization_pld_access_enabled"),
        ("compliance", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PLDEntity",
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
                    "person_type",
                    models.CharField(
                        choices=[
                            ("persona_fisica", "Persona fisica"),
                            ("persona_moral", "Persona moral"),
                        ],
                        max_length=32,
                    ),
                ),
                (
                    "relationship",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("cliente", "Cliente"),
                            ("proveedor", "Proveedor"),
                            ("ambos", "Cliente y proveedor"),
                        ],
                        help_text="Null means this row is the organization itself.",
                        max_length=32,
                        null=True,
                    ),
                ),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pld_entities",
                        to="authenticate.organization",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="pld_entities",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "PLD entity",
                "verbose_name_plural": "PLD entities",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="PLDExpedient",
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
                ("started_at", models.DateTimeField(blank=True, null=True)),
                (
                    "vulnerable_activity",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("activos_virtuales", "Activos virtuales"),
                            ("mutuo_prestamo", "Mutuo, prestamo o credito"),
                            ("inmuebles", "Inmuebles"),
                            ("vehiculos", "Vehiculos"),
                            ("donativos", "Donativos"),
                            ("comercio_exterior", "Comercio exterior"),
                            ("other", "Otra"),
                        ],
                        default="",
                        max_length=64,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("data_collection", "Data collection"),
                            ("document_collection", "Document collection"),
                            ("cross_reference", "Cross reference"),
                            ("waiting_sign", "Waiting signature"),
                            ("signed", "Signed"),
                            ("delivered", "Delivered"),
                            ("action_required", "Action required"),
                        ],
                        db_index=True,
                        default="data_collection",
                        max_length=32,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "entity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="expedients",
                        to="compliance.pldentity",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pld_expedients",
                        to="authenticate.organization",
                    ),
                ),
            ],
            options={
                "verbose_name": "PLD expedient",
                "verbose_name_plural": "PLD expedients",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.AddIndex(
            model_name="pldentity",
            index=models.Index(
                fields=["organization", "relationship"],
                name="compliance_pld_ent_org_rel",
            ),
        ),
        migrations.AddConstraint(
            model_name="pldentity",
            constraint=models.UniqueConstraint(
                condition=models.Q(("relationship__isnull", True)),
                fields=("organization",),
                name="unique_pld_self_entity_per_org",
            ),
        ),
        migrations.AddIndex(
            model_name="pldexpedient",
            index=models.Index(
                fields=["organization", "status"],
                name="compliance_pld_exp_org_st",
            ),
        ),
        migrations.AddConstraint(
            model_name="pldexpedient",
            constraint=models.UniqueConstraint(
                fields=("organization", "entity"),
                name="unique_pld_expedient_per_org_entity",
            ),
        ),
    ]
