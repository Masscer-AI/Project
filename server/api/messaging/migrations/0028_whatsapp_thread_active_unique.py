# Generated manually for WhatsApp /clear (one active thread per phone per line)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("messaging", "0027_conversationtakeover"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="conversation",
            name="uniq_whatsapp_thread",
        ),
        migrations.AddConstraint(
            model_name="conversation",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("ws_number__isnull", False),
                    ("whatsapp_user_number__isnull", False),
                    ("status", "active"),
                ),
                fields=("ws_number", "whatsapp_user_number"),
                name="uniq_whatsapp_thread_active",
            ),
        ),
    ]
