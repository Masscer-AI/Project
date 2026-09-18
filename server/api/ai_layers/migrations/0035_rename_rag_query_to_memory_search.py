from django.db import migrations

OLD = "rag_query"
NEW = "memory_search"


def _rename_in_string_list(value):
    if not isinstance(value, list):
        return value, False
    changed = False
    out = []
    seen = set()
    for item in value:
        if not isinstance(item, str):
            out.append(item)
            continue
        name = NEW if item == OLD else item
        if name == NEW and item == OLD:
            changed = True
        if name in seen:
            changed = True
            continue
        seen.add(name)
        out.append(name)
    return out, changed


def forwards(apps, schema_editor):
    Agent = apps.get_model("ai_layers", "Agent")
    MCPClient = apps.get_model("ai_layers", "MCPClient")

    for agent in Agent.objects.all().iterator():
        tools, changed = _rename_in_string_list(agent.pre_approved_tools)
        if changed:
            agent.pre_approved_tools = tools
            agent.save(update_fields=["pre_approved_tools"])

    for client in MCPClient.objects.all().iterator():
        tools, changed = _rename_in_string_list(client.allowed_tool_names)
        if changed:
            client.allowed_tool_names = tools
            client.save(update_fields=["allowed_tool_names"])


def backwards(apps, schema_editor):
    Agent = apps.get_model("ai_layers", "Agent")
    MCPClient = apps.get_model("ai_layers", "MCPClient")

    def revert(value):
        if not isinstance(value, list):
            return value, False
        changed = False
        out = []
        for item in value:
            if item == NEW:
                out.append(OLD)
                changed = True
            else:
                out.append(item)
        return out, changed

    for agent in Agent.objects.all().iterator():
        tools, changed = revert(agent.pre_approved_tools)
        if changed:
            agent.pre_approved_tools = tools
            agent.save(update_fields=["pre_approved_tools"])

    for client in MCPClient.objects.all().iterator():
        tools, changed = revert(client.allowed_tool_names)
        if changed:
            client.allowed_tool_names = tools
            client.save(update_fields=["allowed_tool_names"])


class Migration(migrations.Migration):
    dependencies = [
        ("ai_layers", "0034_agent_created_at_updated_at"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
