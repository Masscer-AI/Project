# Generated manually for scheduled task title

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("messaging", "0032_conversation_ws_contact"),
    ]

    operations = [
        migrations.AddField(
            model_name="scheduledconversationtask",
            name="title",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Short human-readable label for the scheduled task.",
                max_length=120,
            ),
        ),
        migrations.AlterField(
            model_name="scheduledconversationtask",
            name="instruction_text",
            field=models.TextField(
                help_text=(
                    "Step-by-step execution plan injected when the schedule fires "
                    "(not a natural-language user request)."
                ),
            ),
        ),
    ]
