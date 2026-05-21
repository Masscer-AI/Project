# WSNumber: optional user; organization ownership for access and billing context.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def forwards_backfill_organization(apps, schema_editor):
    Organization = apps.get_model("authenticate", "Organization")
    UserProfile = apps.get_model("authenticate", "UserProfile")
    WSNumber = apps.get_model("whatsapp", "WSNumber")

    def org_id_for_user(user_id):
        oid = Organization.objects.filter(owner_id=user_id).values_list("id", flat=True).first()
        if oid:
            return oid
        prof = UserProfile.objects.filter(user_id=user_id).only("organization_id").first()
        if prof and prof.organization_id:
            return prof.organization_id
        return None

    for ws in WSNumber.objects.filter(organization__isnull=True).iterator():
        if not ws.user_id:
            continue
        oid = org_id_for_user(ws.user_id)
        if oid:
            ws.organization_id = oid
            ws.save(update_fields=["organization_id", "updated_at"])


def backwards_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("whatsapp", "0012_remove_legacy_whatsapp_models"),
        ("authenticate", "0023_organizationmanagementproxy"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="wsnumber",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="whatsapp_numbers",
                to="authenticate.organization",
            ),
        ),
        migrations.AlterField(
            model_name="wsnumber",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="whatsapp_numbers",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(forwards_backfill_organization, backwards_noop),
    ]
