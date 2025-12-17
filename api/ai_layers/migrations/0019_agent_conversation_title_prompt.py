# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_layers', '0018_alter_languagemodel_pricing'),
    ]

    operations = [
        migrations.AddField(
            model_name='agent',
            name='conversation_title_prompt',
            field=models.TextField(blank=True, help_text='Prompt personalizado para generar títulos de conversaciones. Si está vacío, se usa el prompt por defecto.', null=True),
        ),
    ]

