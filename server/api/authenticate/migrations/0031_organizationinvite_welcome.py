from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authenticate", "0030_organization_language_model_list"),
    ]

    operations = [
        migrations.AddField(
            model_name="organizationinvite",
            name="send_welcome_message",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="organizationinvite",
            name="welcome_help_text",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="organizationinvite",
            name="welcome_language",
            field=models.CharField(blank=True, default="en", max_length=8),
        ),
        migrations.AddField(
            model_name="organizationinvite",
            name="welcome_line_ids",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="organizationinvite",
            name="welcome_phones",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
