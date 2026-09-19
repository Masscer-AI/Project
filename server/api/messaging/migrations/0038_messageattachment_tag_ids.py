from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("messaging", "0037_rename_rag_query_to_memory_search"),
    ]

    operations = [
        migrations.AddField(
            model_name="messageattachment",
            name="tag_ids",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Organization tag ids (same catalog as conversation tags).",
            ),
        ),
    ]
