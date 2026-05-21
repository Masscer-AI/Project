# Generated manually for WhatsApp agent-task migration

from django.db import migrations, models


def forwards_default_capabilities(apps, schema_editor):
    WSNumber = apps.get_model("whatsapp", "WSNumber")
    default_tools = ("rag_query", "explore_web", "read_attachment", "list_attachments")
    for ws in WSNumber.objects.all():
        caps = list(ws.capabilities or [])
        names = {
            c.get("name")
            for c in caps
            if isinstance(c, dict) and isinstance(c.get("name"), str)
        }
        changed = False
        for tool in default_tools:
            if tool not in names:
                caps.append(
                    {"name": tool, "type": "internal_tool", "enabled": True}
                )
                names.add(tool)
                changed = True
        if changed:
            ws.capabilities = caps
            ws.save(update_fields=["capabilities", "updated_at"])


def backwards_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("whatsapp", "0010_wsnumber_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="wsnumber",
            name="capabilities",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(forwards_default_capabilities, backwards_noop),
    ]
