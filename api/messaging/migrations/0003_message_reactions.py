# Generated by Django 5.1.1 on 2024-11-03 19:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('messaging', '0002_message_browse_sources_message_rag_sources_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='reactions',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
