from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("messaging", "0022_chatwidget_default_attachment_capabilities"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="metadata",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Structured metadata (validated via ConversationMetadata schema), e.g. related_agents",
            ),
        ),
    ]
