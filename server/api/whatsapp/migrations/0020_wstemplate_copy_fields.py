from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("whatsapp", "0019_alter_wsnumber_allowed_roles"),
    ]

    operations = [
        migrations.AddField(
            model_name="wstemplate",
            name="header_text",
            field=models.CharField(blank=True, default="", max_length=60),
        ),
        migrations.AddField(
            model_name="wstemplate",
            name="body_text",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="wstemplate",
            name="footer_text",
            field=models.CharField(blank=True, default="", max_length=60),
        ),
        migrations.AlterField(
            model_name="wstemplate",
            name="buttons",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    "List of {index, sub_type, use_source_conversation_id, "
                    "label, url, description}."
                ),
            ),
        ),
    ]
