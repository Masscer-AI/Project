# Generated by Django 5.1.1 on 2024-09-27 19:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authenticate', '0003_alter_publishabletoken_token'),
    ]

    operations = [
        migrations.AlterField(
            model_name='publishabletoken',
            name='token',
            field=models.CharField(default='7900c50c3e404f8dba57212dc04925ec', max_length=255, unique=True),
        ),
    ]
