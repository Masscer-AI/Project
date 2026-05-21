# Optional WABA id for Graph webhook admin actions.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("whatsapp", "0013_wsnumber_organization_optional_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="wsnumber",
            name="waba_id",
            field=models.CharField(
                blank=True,
                help_text="WhatsApp Business Account id (optional). Used for admin webhook setup; "
                "left blank it is resolved from platform_id via Graph when possible.",
                max_length=100,
                null=True,
            ),
        ),
    ]
