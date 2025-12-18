# Generated manually

from django.db import migrations, models
import pytz


class Migration(migrations.Migration):

    dependencies = [
        ('authenticate', '0013_alter_userprofile_organization'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='timezone',
            field=models.CharField(
                default='UTC',
                help_text='Zona horaria de la organización para mostrar timestamps',
                max_length=50,
                choices=[(tz, tz) for tz in pytz.all_timezones]
            ),
        ),
    ]

