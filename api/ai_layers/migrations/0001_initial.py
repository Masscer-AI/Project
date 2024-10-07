# Generated by Django 5.1.1 on 2024-09-30 16:23

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Agent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('slug', models.SlugField(blank=True, unique=True)),
                ('model_slug', models.CharField(max_length=100)),
                ('system_prompt', models.TextField()),
                ('salute', models.TextField()),
                ('act_as', models.TextField(help_text='How should the AI act?')),
            ],
        ),
        migrations.CreateModel(
            name='ModelConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('temperature', models.FloatField(validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(2.0)])),
                ('max_tokens', models.IntegerField()),
                ('top_p', models.FloatField(validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('frequency_penalty', models.FloatField(validators=[django.core.validators.MinValueValidator(-2.0), django.core.validators.MaxValueValidator(2.0)])),
                ('presence_penalty', models.FloatField(validators=[django.core.validators.MinValueValidator(-2.0), django.core.validators.MaxValueValidator(2.0)])),
            ],
        ),
    ]