# Generated by Django 5.1.1 on 2024-10-10 22:34

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('providers', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameModel(
            old_name='ProviderCredentials',
            new_name='AIProviderCredentials',
        ),
    ]
