from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("compliance", "0018_pldmatrix"),
    ]

    operations = [
        migrations.AddField(
            model_name="pldentity",
            name="ppe_screening_enabled",
            field=models.BooleanField(
                default=False,
                help_text="When true, screen the representative and beneficial owners as politically exposed persons.",
            ),
        ),
        migrations.AddField(
            model_name="pldexpedient",
            name="ppe_payload",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="pldexpedient",
            name="ppe_screened_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="pldexpedient",
            name="ppe_status",
            field=models.CharField(blank=True, default="", max_length=16),
        ),
    ]
