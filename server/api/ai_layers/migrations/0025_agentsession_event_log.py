from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_layers', '0024_alter_agent_model_provider'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentsession',
            name='event_log',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
