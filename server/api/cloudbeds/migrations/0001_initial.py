from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("authenticate", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CloudbedsCredential",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("access_token", models.TextField(help_text="Cloudbeds OAuth access token.")),
                ("refresh_token", models.TextField(blank=True, default="", help_text="Cloudbeds OAuth refresh token (used to obtain a new access token).")),
                ("token_type", models.CharField(default="Bearer", max_length=50)),
                ("expires_at", models.DateTimeField(blank=True, help_text="UTC datetime when the access_token expires. Null = non-expiring.", null=True)),
                ("property_id", models.CharField(blank=True, default="", help_text="Cloudbeds property ID associated with this token.", max_length=100)),
                ("property_name", models.CharField(blank=True, default="", help_text="Display name of the connected Cloudbeds property.", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cloudbeds_credential",
                        to="authenticate.organization",
                    ),
                ),
            ],
            options={
                "verbose_name": "Cloudbeds Credential",
                "verbose_name_plural": "Cloudbeds Credentials",
            },
        ),
    ]
