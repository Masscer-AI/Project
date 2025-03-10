# Generated by Django 5.1.1 on 2024-10-10 22:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('providers', '0002_rename_providercredentials_aiprovidercredentials'),
    ]

    operations = [
        migrations.CreateModel(
            name='SearchEngineProvider',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('website_url', models.URLField(blank=True, null=True)),
                ('docs_url', models.URLField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
