# Generated manually

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authenticate', '0009_featureflag_featureflagassignment'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                help_text='Organización a la que pertenece el usuario',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='members',
                to='authenticate.organization'
            ),
        ),
    ]

