# Generated manually to add color field to Tag model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('messaging', '0011_alter_conversation_tags'),
    ]

    operations = [
        migrations.AddField(
            model_name='tag',
            name='color',
            field=models.CharField(default='#4a9eff', help_text='Color de la etiqueta en formato hexadecimal', max_length=7),
        ),
    ]

