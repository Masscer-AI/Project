from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compliance", "0006_pldexpedientdocument"),
    ]

    operations = [
        migrations.AddField(
            model_name="pldexpedientdocument",
            name="extracted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="pldexpedientdocument",
            name="extracted_payload",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="pldexpedientdocument",
            name="extraction_error",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
        migrations.AddField(
            model_name="pldexpedientdocument",
            name="extraction_status",
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
    ]
