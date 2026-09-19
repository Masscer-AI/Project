from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("rag", "0014_alter_document_allowed_roles"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="tag_ids",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Organization tag ids (same catalog as conversation tags).",
            ),
        ),
    ]
