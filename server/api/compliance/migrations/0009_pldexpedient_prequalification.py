from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compliance", "0008_pldexpedientdocument_file_sha256"),
    ]

    operations = [
        migrations.AddField(
            model_name="pldexpedient",
            name="prequalification_payload",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="pldexpedient",
            name="prequalification_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("pending", "Pending"),
                    ("succeeded", "Succeeded"),
                    ("failed", "Failed"),
                ],
                default="",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="pldexpedient",
            name="prequalified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
