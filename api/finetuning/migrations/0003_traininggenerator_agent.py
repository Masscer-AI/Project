# Generated by Django 5.1.1 on 2024-10-28 06:15

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_layers', '0009_agent_llm'),
        ('finetuning', '0002_completion_agent_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='traininggenerator',
            name='agent',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='ai_layers.agent'),
        ),
    ]
