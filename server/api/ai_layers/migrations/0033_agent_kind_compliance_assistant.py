# Generated manually for compliance assistant support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai_layers", "0032_alter_agent_pre_approved_tools"),
    ]

    operations = [
        migrations.AlterField(
            model_name="agent",
            name="agent_kind",
            field=models.CharField(
                choices=[
                    ("conversational_agent", "Conversational agent"),
                    ("platform_assistant", "Platform assistant"),
                    ("compliance_assistant", "Compliance assistant"),
                ],
                default="conversational_agent",
                max_length=32,
            ),
        ),
        migrations.AddConstraint(
            model_name="agent",
            constraint=models.UniqueConstraint(
                condition=models.Q(("agent_kind", "compliance_assistant")),
                fields=("organization",),
                name="unique_compliance_assistant_per_org",
            ),
        ),
    ]
