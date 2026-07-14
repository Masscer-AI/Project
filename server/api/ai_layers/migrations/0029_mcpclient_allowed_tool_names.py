from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai_layers", "0028_mcpclient"),
    ]

    operations = [
        migrations.AddField(
            model_name="mcpclient",
            name="allowed_tool_names",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    "Agent tools enabled for runs via this credential. "
                    "Empty = basic MCP preset."
                ),
            ),
        ),
    ]
