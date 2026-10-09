from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("esign", "0004_signaturesigner"),
    ]

    operations = [
        migrations.CreateModel(
            name="JaakWebhookInbox",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("content_type", models.CharField(blank=True, default="", max_length=128)),
                ("body", models.TextField(blank=True, default="")),
                ("received_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-received_at"],
            },
        ),
    ]
