from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("compliance", "0015_pldexpedient_packet_and_signature"),
    ]

    operations = [
        migrations.AddField(
            model_name="pldexpedient",
            name="risk_payload",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="pldexpedient",
            name="risk_status",
            field=models.CharField(blank=True, default="", max_length=16),
        ),
        migrations.AddField(
            model_name="pldexpedient",
            name="risked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
