from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("messaging", "0019_chatwidget_capabilities_first_message"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatwidget",
            name="avatar_image",
            field=models.URLField(blank=True, default="", max_length=500),
        ),
    ]
