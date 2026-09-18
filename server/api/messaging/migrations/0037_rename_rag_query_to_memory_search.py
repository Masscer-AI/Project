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
    ChatWidget = apps.get_model("messaging", "ChatWidget")
    ScheduledConversationTask = apps.get_model(
        "messaging", "ScheduledConversationTask"
    )

    for widget in ChatWidget.objects.all().iterator():
        caps, changed = _rename_in_capabilities(widget.capabilities)
        if changed:
            widget.capabilities = caps
            widget.save(update_fields=["capabilities"])

    for task in ScheduledConversationTask.objects.all().iterator():
        caps, changed = _rename_in_capabilities(getattr(task, "capabilities", None))
        if changed:
            task.capabilities = caps
            task.save(update_fields=["capabilities"])


def backwards(apps, schema_editor):
    ChatWidget = apps.get_model("messaging", "ChatWidget")
    ScheduledConversationTask = apps.get_model(
        "messaging", "ScheduledConversationTask"
    )

    def revert(value):
        if not isinstance(value, list):
            return value, False
        changed = False
        out = []
        for cap in value:
            if isinstance(cap, dict) and cap.get("name") == NEW:
                item = dict(cap)
                item["name"] = OLD
                out.append(item)
                changed = True
            else:
                out.append(cap)
        return out, changed

    for widget in ChatWidget.objects.all().iterator():
        caps, changed = revert(widget.capabilities)
        if changed:
            widget.capabilities = caps
            widget.save(update_fields=["capabilities"])

    for task in ScheduledConversationTask.objects.all().iterator():
        caps, changed = revert(getattr(task, "capabilities", None))
        if changed:
            task.capabilities = caps
            task.save(update_fields=["capabilities"])


class Migration(migrations.Migration):
    dependencies = [
        ("messaging", "0036_messageattachment_visibility_db_default"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
