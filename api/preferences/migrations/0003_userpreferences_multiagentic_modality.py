# Generated by Django 5.1.1 on 2024-11-25 00:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('preferences', '0002_userpreferences_theme'),
    ]

    operations = [
        migrations.AddField(
            model_name='userpreferences',
            name='multiagentic_modality',
            field=models.CharField(choices=[('isolated', 'Isolated'), ('grupal', 'Grupal')], default='isolated', max_length=50),
        ),
    ]
