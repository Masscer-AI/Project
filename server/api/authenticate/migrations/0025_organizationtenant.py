from django.db import migrations, models
import django.db.models.deletion


def copy_subdomains_to_tenant(apps, schema_editor):
    Organization = apps.get_model("authenticate", "Organization")
    OrganizationTenant = apps.get_model("authenticate", "OrganizationTenant")

    for org in Organization.objects.exclude(subdomain__isnull=True).exclude(subdomain=""):
        OrganizationTenant.objects.create(
            organization_id=org.id,
            subdomain=org.subdomain,
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("authenticate", "0024_organization_subdomain"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrganizationTenant",
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
                    "subdomain",
                    models.SlugField(
                        blank=True,
                        help_text="Claimed tenant subdomain (e.g. acme for acme.masscer.ai)",
                        max_length=63,
                        null=True,
                        unique=True,
                    ),
                ),
                (
                    "app_name",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Portal display name; blank falls back to organization.name",
                        max_length=255,
                    ),
                ),
                ("theme", models.JSONField(blank=True, default=dict)),
                ("hide_powered_by", models.BooleanField(default=False)),
                (
                    "favicon",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to="organizations/tenants/favicons/",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tenant",
                        to="authenticate.organization",
                    ),
                ),
            ],
        ),
        migrations.RunPython(copy_subdomains_to_tenant, noop_reverse),
        migrations.RemoveField(
            model_name="organization",
            name="subdomain",
        ),
    ]
