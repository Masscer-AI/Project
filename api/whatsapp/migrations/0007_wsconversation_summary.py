# Generated by Django 5.1.1 on 2024-10-27 07:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp', '0006_wscontact_collected_info_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='wsconversation',
            name='summary',
            field=models.TextField(blank=True, null=True),
        ),
    ]
