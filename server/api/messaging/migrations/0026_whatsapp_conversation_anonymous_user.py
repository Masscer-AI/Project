# WhatsApp threads: anonymous like chat widgets (no Conversation.user).

from django.db import migrations


def forwards_clear_whatsapp_conversation_user(apps, schema_editor):
    Conversation = apps.get_model("messaging", "Conversation")
    Conversation.objects.filter(ws_number__isnull=False).update(user_id=None)


def backwards_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("messaging", "0025_remove_conversation_uniq_whatsapp_thread_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards_clear_whatsapp_conversation_user, backwards_noop),
    ]
