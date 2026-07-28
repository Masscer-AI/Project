# Generated manually for WSContact bridge

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("whatsapp", "0015_alter_wsnumber_number"),
    ]

    operations = [
        migrations.CreateModel(
            name="WSContact",
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
                    "number",
                    models.CharField(
                        help_text="Visitor phone digits (country code included). Normalized on save.",
                        max_length=30,
                    ),
                ),
                (
                    "display_name",
                    models.CharField(blank=True, default="", max_length=100),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="whatsapp_contacts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "ws_number",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contacts",
                        to="whatsapp.wsnumber",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="wscontact",
            constraint=models.UniqueConstraint(
                fields=("ws_number", "number"),
                name="uniq_wscontact_ws_number_number",
            ),
        ),
    ]
