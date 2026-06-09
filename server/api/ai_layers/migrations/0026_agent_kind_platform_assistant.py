# Generated manually for platform assistant support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai_layers", "0025_agentsession_event_log"),
    ]

    operations = [
        migrations.AddField(
            model_name="agent",
            name="agent_kind",
            field=models.CharField(
                choices=[
                    ("conversational_agent", "Conversational agent"),
                    ("platform_assistant", "Platform assistant"),
                ],
                default="conversational_agent",
                max_length=32,
            ),
        ),
        migrations.RemoveField(
            model_name="agent",
            name="frequency_penalty",
        ),
        migrations.RemoveField(
            model_name="agent",
            name="presence_penalty",
        ),
        migrations.RemoveField(
            model_name="agent",
            name="temperature",
        ),
        migrations.RemoveField(
            model_name="agent",
            name="top_p",
        ),
        migrations.AddConstraint(
            model_name="agent",
            constraint=models.UniqueConstraint(
                condition=models.Q(("agent_kind", "platform_assistant")),
                fields=("organization",),
                name="unique_platform_assistant_per_org",
            ),
        ),
    ]
