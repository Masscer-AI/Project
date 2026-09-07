from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compliance", "0007_pldexpedientdocument_extraction"),
    ]

    operations = [
        migrations.AddField(
            model_name="pldexpedientdocument",
            name="file_sha256",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
    ]
