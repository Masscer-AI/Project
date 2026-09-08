import django.db.models.deletion
from django.db import migrations, models

import api.compliance.models


class Migration(migrations.Migration):
    dependencies = [
        ("compliance", "0014_rename_compliance__expedie_clar_idx_compliance__expedie_f67682_idx"),
        ("esign", "0003_signaturerequest_source_file_optional"),
    ]

    operations = [
        migrations.AddField(
            model_name="pldexpedient",
            name="packet_file",
            field=models.FileField(
                blank=True,
                default="",
                upload_to=api.compliance.models.pld_expedient_packet_upload_to,
            ),
        ),
        migrations.AddField(
            model_name="pldexpedient",
            name="packet_generated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="pldexpedient",
            name="signed_packet",
            field=models.FileField(
                blank=True,
                default="",
                upload_to=api.compliance.models.pld_expedient_packet_upload_to,
            ),
        ),
        migrations.AddField(
            model_name="pldexpedient",
            name="signed_packet_xml",
            field=models.FileField(
                blank=True,
                default="",
                upload_to=api.compliance.models.pld_expedient_packet_upload_to,
            ),
        ),
        migrations.AddField(
            model_name="pldexpedient",
            name="signature_request",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="pld_expedients",
                to="esign.signaturerequest",
            ),
        ),
    ]
