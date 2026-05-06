from django.db import migrations


def forwards_default_attachment_capabilities(apps, schema_editor):
    ChatWidget = apps.get_model("messaging", "ChatWidget")
    for widget in ChatWidget.objects.all():
        caps = list(widget.capabilities or [])
        names = {
            c.get("name")
            for c in caps
            if isinstance(c, dict) and isinstance(c.get("name"), str)
        }
        changed = False
        for tool in ("read_attachment", "list_attachments"):
            if tool not in names:
                caps.append(
                    {"name": tool, "type": "internal_tool", "enabled": True}
                )
                names.add(tool)
                changed = True
        if changed:
            widget.capabilities = caps
            widget.save(update_fields=["capabilities", "updated_at"])


def backwards_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("messaging", "0021_alter_chatwidget_avatar_image"),
    ]

    operations = [
        migrations.RunPython(forwards_default_attachment_capabilities, backwards_noop),
    ]
