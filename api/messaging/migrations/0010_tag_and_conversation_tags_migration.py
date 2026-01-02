# Generated manually for Tag model and Conversation.tags migration

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authenticate', '0009_featureflag_featureflagassignment'),
        ('messaging', '0009_conversation_pending_analysis_conversation_summary_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Create Tag model
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('title', models.CharField(help_text='Título de la etiqueta (máximo 50 caracteres)', max_length=50)),
                ('description', models.TextField(blank=True, help_text='Descripción detallada de la etiqueta')),
                ('enabled', models.BooleanField(default=True, help_text='Indica si la etiqueta está habilitada')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('organization', models.ForeignKey(help_text='Organización a la que pertenece esta etiqueta', on_delete=django.db.models.deletion.CASCADE, related_name='tags', to='authenticate.organization')),
            ],
            options={
                'verbose_name': 'Tag',
                'verbose_name_plural': 'Tags',
                'ordering': ['title'],
                'unique_together': {('title', 'organization')},
            },
        ),
        # El campo tags ya existe como JSONField desde la migración 0007, no necesita cambios
        # Solo actualizamos el help_text si es necesario (esto se puede hacer en una migración separada o manualmente)
    ]

