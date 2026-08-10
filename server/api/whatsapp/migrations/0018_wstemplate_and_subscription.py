# Generated manually for WSTemplate + WSTemplateSubscription

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authenticate", "0026_userprofile__phone_numbers"),
        ("whatsapp", "0017_wsnumber_access_scope"),
    ]

    operations = [
        migrations.CreateModel(
            name="WSTemplate",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "slug",
                    models.CharField(
                        help_text=(
                            "Stable local template id (registry id), "
                            "e.g. task_completed_en."
                        ),
                        max_length=100,
                        unique=True,
                    ),
                ),
                ("meta_name", models.CharField(max_length=200)),
                ("language_code", models.CharField(max_length=20)),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("UTILITY", "Utility"),
                            ("MARKETING", "Marketing"),
                            ("AUTHENTICATION", "Authentication"),
                        ],
                        default="UTILITY",
                        max_length=20,
                    ),
                ),
                ("description", models.TextField(blank=True, default="")),
                (
                    "header_type",
                    models.CharField(
                        choices=[
                            ("none", "None"),
                            ("text", "Text"),
                            ("image", "Image"),
                        ],
                        default="none",
                        max_length=10,
                    ),
                ),
                ("body_variable_count", models.PositiveIntegerField(default=0)),
                (
                    "body_variable_descriptions",
                    models.JSONField(blank=True, default=list),
                ),
                (
                    "buttons",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text=(
                            "List of {index, sub_type, "
                            "use_source_conversation_id, description}."
                        ),
                    ),
                ),
                ("enabled", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["slug"],
            },
        ),
        migrations.CreateModel(
            name="WSTemplateSubscription",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="whatsapp_template_subscriptions",
                        to="authenticate.organization",
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subscriptions",
                        to="whatsapp.wstemplate",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="wstemplatesubscription",
            constraint=models.UniqueConstraint(
                fields=("template", "organization"),
                name="uniq_wstemplate_subscription_template_org",
            ),
        ),
    ]
