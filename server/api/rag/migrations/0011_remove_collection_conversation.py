from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("rag", "0010_document_content_type_document_file"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="collection",
            name="conversation",
        ),
    ]
