from django.db import migrations, models

import api.messaging.models


class Migration(migrations.Migration):
    dependencies = [
        ("messaging", "0028_whatsapp_thread_active_unique"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatwidget",
            name="avatar",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to=api.messaging.models.chat_widget_avatar_upload_path,
            ),
        ),
    ]
