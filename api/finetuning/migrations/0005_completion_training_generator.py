# Generated by Django 5.1.1 on 2024-10-28 06:21

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finetuning', '0004_remove_traininggenerator_generation_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='completion',
            name='training_generator',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='finetuning.traininggenerator'),
        ),
    ]
