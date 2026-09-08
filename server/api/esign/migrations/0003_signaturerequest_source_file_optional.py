from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("esign", "0002_signaturerequest_provider_widget_id"),
        ("messaging", "0036_messageattachment_visibility_db_default"),
    ]

    operations = [
        migrations.AlterField(
            model_name="signaturerequest",
            name="source_file",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Unsigned PDF from a conversation, when the request did not "
                    "come from a PLD expediente."
                ),
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="signature_requests_as_source",
                to="messaging.messageattachment",
            ),
        ),
    ]
