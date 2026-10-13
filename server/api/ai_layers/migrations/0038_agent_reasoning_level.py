from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai_layers", "0037_languagemodel_reasoning_levels"),
    ]

    operations = [
        migrations.AddField(
            model_name="agent",
            name="reasoning_level",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
    ]
