from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authenticate", "0028_organizationinvite_role"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="pld_access_enabled",
            field=models.BooleanField(
                default=False,
                help_text="When true, this organization can use the PLD / compliance hub.",
            ),
        ),
    ]
