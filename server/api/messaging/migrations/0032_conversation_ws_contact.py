# Generated manually for WSContact bridge + backfill

import django.db.models.deletion
from django.db import migrations, models


def backfill_ws_contacts(apps, schema_editor):
    Conversation = apps.get_model("messaging", "Conversation")
    WSContact = apps.get_model("whatsapp", "WSContact")

    pairs = (
        Conversation.objects.filter(ws_number_id__isnull=False)
        .exclude(whatsapp_user_number__isnull=True)
        .exclude(whatsapp_user_number="")
        .values_list("ws_number_id", "whatsapp_user_number")
        .distinct()
    )

    contact_by_key: dict[tuple[int, str], int] = {}
    for ws_number_id, phone in pairs:
        digits = "".join(c for c in (phone or "") if c.isdigit())
        if not digits:
            continue
        key = (ws_number_id, digits)
        if key in contact_by_key:
            continue
        contact, _ = WSContact.objects.get_or_create(
            ws_number_id=ws_number_id,
            number=digits,
            defaults={"display_name": ""},
        )
        contact_by_key[key] = contact.id

    for (ws_number_id, digits), contact_id in contact_by_key.items():
        Conversation.objects.filter(
            ws_number_id=ws_number_id,
            whatsapp_user_number=digits,
        ).update(ws_contact_id=contact_id)
        # Also match rows that still have formatting in whatsapp_user_number
        # if any non-digit variants exist for the same logical phone.
        for conv in Conversation.objects.filter(
            ws_number_id=ws_number_id,
            ws_contact_id__isnull=True,
        ).exclude(whatsapp_user_number__isnull=True).exclude(whatsapp_user_number=""):
            conv_digits = "".join(
                c for c in (conv.whatsapp_user_number or "") if c.isdigit()
            )
            if conv_digits == digits:
                Conversation.objects.filter(pk=conv.pk).update(ws_contact_id=contact_id)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("messaging", "0031_scheduled_task_capabilities"),
        ("whatsapp", "0016_wscontact"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="ws_contact",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="conversations",
                to="whatsapp.wscontact",
            ),
        ),
        migrations.RunPython(backfill_ws_contacts, noop_reverse),
    ]
