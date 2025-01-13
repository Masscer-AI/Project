# Generated by Django 5.1.1 on 2025-01-13 07:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consumption', '0002_rename_computeunit_currency'),
    ]

    operations = [
        migrations.AlterField(
            model_name='consumption',
            name='amount',
            field=models.DecimalField(decimal_places=8, default=0.1, max_digits=12),
        ),
        migrations.AlterField(
            model_name='wallet',
            name='balance',
            field=models.DecimalField(decimal_places=8, default=0, max_digits=12),
        ),
    ]
