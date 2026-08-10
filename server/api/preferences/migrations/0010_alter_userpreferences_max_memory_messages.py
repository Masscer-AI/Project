from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("preferences", "0009_userpreferences_notification_settings"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userpreferences",
            name="max_memory_messages",
            field=models.IntegerField(default=100),
        ),
    ]
