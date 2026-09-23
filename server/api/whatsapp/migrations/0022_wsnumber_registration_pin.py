from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("whatsapp", "0021_rename_rag_query_to_memory_search"),
    ]

    operations = [
        migrations.AddField(
            model_name="wsnumber",
            name="registration_pin",
            field=models.CharField(
                blank=True,
                help_text="Six-digit two-step PIN sent to Meta when this number was registered.",
                max_length=6,
                null=True,
            ),
        ),
    ]
