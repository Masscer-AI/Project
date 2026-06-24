from django.db import migrations, models

import api.preferences.notification_settings


class Migration(migrations.Migration):

    dependencies = [
        ("preferences", "0008_delete_usertags"),
    ]

    operations = [
        migrations.AddField(
            model_name="userpreferences",
            name="notification_settings",
            field=models.JSONField(
                default=api.preferences.notification_settings.default_notification_settings_dict
            ),
        ),
    ]
