# Generated by Django 5.1.1 on 2024-10-07 20:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tools', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='transcriptionjob',
            name='whisper_size',
            field=models.CharField(choices=[('LARGE', 'Large'), ('MEDIUM', 'Medium'), ('TINY', 'Tiny')], default='LARGE', max_length=6),
        ),
    ]
