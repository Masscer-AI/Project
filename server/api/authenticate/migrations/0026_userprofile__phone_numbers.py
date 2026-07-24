from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authenticate", "0025_organizationtenant"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="_phone_numbers",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    "Validated phone numbers for the user. "
                    "Use the phone_numbers property for Pydantic-validated access."
                ),
            ),
        ),
    ]
