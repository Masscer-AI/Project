from django.db import migrations

OLD = "rag_query"
NEW = "memory_search"


def _rename_in_capabilities(value):
    if not isinstance(value, list):
        return value, False
    changed = False
    out = []
    seen = set()
    for cap in value:
        if not isinstance(cap, dict):
            out.append(cap)
            continue
        item = dict(cap)
        name = item.get("name")
        if name == OLD:
            item["name"] = NEW
            name = NEW
            changed = True
        if isinstance(name, str):
            if name in seen:
                changed = True
                continue
            seen.add(name)
        out.append(item)
    return out, changed


def forwards(apps, schema_editor):
    WSNumber = apps.get_model("whatsapp", "WSNumber")
    for ws in WSNumber.objects.all().iterator():
        caps, changed = _rename_in_capabilities(ws.capabilities)
        if changed:
            ws.capabilities = caps
            ws.save(update_fields=["capabilities"])


def backwards(apps, schema_editor):
    WSNumber = apps.get_model("whatsapp", "WSNumber")
    for ws in WSNumber.objects.all().iterator():
        caps = ws.capabilities
        if not isinstance(caps, list):
            continue
        changed = False
        out = []
        for cap in caps:
            if isinstance(cap, dict) and cap.get("name") == NEW:
                item = dict(cap)
                item["name"] = OLD
                out.append(item)
                changed = True
            else:
                out.append(cap)
        if changed:
            ws.capabilities = out
            ws.save(update_fields=["capabilities"])


class Migration(migrations.Migration):
    dependencies = [
        ("whatsapp", "0020_wstemplate_copy_fields"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
