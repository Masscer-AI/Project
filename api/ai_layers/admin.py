from django.contrib import admin
from .models import Agent, LanguageModel
from django.utils.safestring import mark_safe
import json


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "user", "is_public")
    search_fields = ("name", "slug", "user__username")


@admin.register(LanguageModel)
class LanguageModelAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "pricing_table",
        "provider",
        "created_at",
        "updated_at",
    )
    search_fields = ("name", "slug", "provider__name")
    list_filter = ("provider",)

    # pricing table
    def pricing_table(self, obj):
        # Show a table with the pricing
        return mark_safe(
            f"""<table >
            <tr>
                <th>Prompt</th>
                <th>Output</th>
            </tr>
            <tr>
                <td>{obj.pricing['text']['prompt']}</td>
                <td>{obj.pricing['text']['output']}</td>
            </tr>
            </table>"""
        )
