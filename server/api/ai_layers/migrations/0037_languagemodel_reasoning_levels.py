from django.db import migrations, models

import api.ai_layers.models


class Migration(migrations.Migration):

    dependencies = [
        ("ai_layers", "0036_languagemodellist"),
    ]

    operations = [
        migrations.AddField(
            model_name="languagemodel",
            name="reasoning_levels",
            field=models.JSONField(
                blank=True,
                default=api.ai_layers.models.default_reasoning_levels,
            ),
        ),
    ]
