# Generated manually — removes unused Brave Search field (replaced by Firecrawl at app level).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("authenticate", "0019_userprofile_expires_at"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="credentialsmanager",
            name="brave_api_key",
        ),
    ]
