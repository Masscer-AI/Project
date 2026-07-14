import uuid

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authenticate", "0025_organizationtenant"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ai_layers", "0027_remove_agent_openai_voice_agent_default_voice"),
    ]

    operations = [
        migrations.CreateModel(
            name="MCPClient",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "key",
                    models.CharField(
                        blank=True, db_index=True, max_length=64, unique=True
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("scopes", models.JSONField(blank=True, default=list)),
                ("revoked", models.BooleanField(default=False)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "allowed_agents",
                    models.ManyToManyField(
                        blank=True,
                        help_text="If empty, all accessible agents are exposed via MCP.",
                        related_name="mcp_clients",
                        to="ai_layers.agent",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="mcp_clients",
                        to="authenticate.organization",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="mcp_clients",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
