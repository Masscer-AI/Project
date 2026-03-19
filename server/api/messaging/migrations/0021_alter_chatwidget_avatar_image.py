from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("messaging", "0020_chatwidget_avatar_image"),
    ]

    operations = [
        migrations.AlterField(
            model_name="chatwidget",
            name="avatar_image",
            field=models.TextField(blank=True, default=""),
        ),
    ]
