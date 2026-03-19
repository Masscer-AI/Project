from django.db import migrations, models


def _forward_migrate_capabilities(apps, schema_editor):
    ChatWidget = apps.get_model("messaging", "ChatWidget")

    for widget in ChatWidget.objects.all():
        capabilities = []

        if getattr(widget, "web_search_enabled", False):
            capabilities.append(
                {"name": "explore_web", "type": "internal_tool", "enabled": True}
            )

        if getattr(widget, "rag_enabled", False):
            capabilities.append(
                {"name": "rag_query", "type": "internal_tool", "enabled": True}
            )

        for tool_name in getattr(widget, "plugins_enabled", []) or []:
            if isinstance(tool_name, str) and tool_name.strip():
                if tool_name.strip() == "print_color":
                    continue
                capabilities.append(
                    {
                        "name": tool_name.strip(),
                        "type": "internal_tool",
                        "enabled": True,
                    }
                )

        deduped_capabilities = []
        seen_names = set()
        for capability in capabilities:
            name = capability["name"]
            if name in seen_names:
                continue
            seen_names.add(name)
            deduped_capabilities.append(capability)

        widget.capabilities = deduped_capabilities
        if widget.first_message is None:
            widget.first_message = ""
        widget.save(update_fields=["capabilities", "first_message", "updated_at"])


def _reverse_migrate_capabilities(apps, schema_editor):
    ChatWidget = apps.get_model("messaging", "ChatWidget")

    for widget in ChatWidget.objects.all():
        capabilities = getattr(widget, "capabilities", []) or []

        web_search_enabled = False
        rag_enabled = False
        plugins_enabled = []

        for capability in capabilities:
            if not isinstance(capability, dict):
                continue
            if capability.get("type") != "internal_tool":
                continue
            if not capability.get("enabled", False):
                continue

            name = capability.get("name")
            if not isinstance(name, str):
                continue

            if name == "explore_web":
                web_search_enabled = True
            elif name == "rag_query":
                rag_enabled = True
            else:
                plugins_enabled.append(name)

        widget.web_search_enabled = web_search_enabled
        widget.rag_enabled = rag_enabled
        widget.plugins_enabled = plugins_enabled
        widget.save(
            update_fields=[
                "web_search_enabled",
                "rag_enabled",
                "plugins_enabled",
                "updated_at",
            ]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("messaging", "0018_chatwidget_style"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatwidget",
            name="first_message",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="chatwidget",
            name="capabilities",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(
            _forward_migrate_capabilities,
            _reverse_migrate_capabilities,
        ),
        migrations.RemoveField(
            model_name="chatwidget",
            name="web_search_enabled",
        ),
        migrations.RemoveField(
            model_name="chatwidget",
            name="rag_enabled",
        ),
        migrations.RemoveField(
            model_name="chatwidget",
            name="plugins_enabled",
        ),
    ]
