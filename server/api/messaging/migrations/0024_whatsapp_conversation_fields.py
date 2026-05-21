# Generated manually for WhatsApp agent-task migration

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("messaging", "0023_conversation_metadata"),
        ("whatsapp", "0011_wsnumber_capabilities"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="ws_number",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="conversations",
                to="whatsapp.wsnumber",
            ),
        ),
        migrations.AddField(
            model_name="conversation",
            name="whatsapp_user_number",
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=30,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="conversation",
            name="whatsapp_last_inbound_wamid",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="message",
            name="metadata",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Channel-specific metadata (e.g. WhatsApp WAMID, reaction emoji)",
            ),
        ),
        migrations.AddConstraint(
            model_name="conversation",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ws_number__isnull=False,
                    whatsapp_user_number__isnull=False,
                ),
                fields=("ws_number", "whatsapp_user_number"),
                name="uniq_whatsapp_thread",
            ),
        ),
    ]
