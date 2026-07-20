# Generated manually for google_calendar provider choice

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="integration",
            name="provider",
            field=models.CharField(
                choices=[
                    ("google_drive", "Google Drive"),
                    ("google_calendar", "Google Calendar"),
                ],
                max_length=64,
            ),
        ),
    ]
