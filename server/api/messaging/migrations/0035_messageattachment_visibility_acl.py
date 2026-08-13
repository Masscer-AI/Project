# Generated manually for MessageAttachment visibility ACL and SET_NULL FKs.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def backfill_personal_visibility(apps, schema_editor):
    MessageAttachment = apps.get_model("messaging", "MessageAttachment")
    MessageAttachment.objects.filter(visibility__isnull=True).update(
        visibility="personal"
    )
    MessageAttachment.objects.exclude(
        visibility__in=("personal", "organization", "roles", "link")
    ).update(visibility="personal")


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("ai_layers", "0030_agent_pre_approved_tools"),
        ("authenticate", "0026_userprofile__phone_numbers"),
        ("messaging", "0034_alter_scheduledconversationtask_capabilities"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="messageattachment",
            name="agent",
            field=models.ForeignKey(
                blank=True,
                help_text="Agent that generated this file, if any. Attribution only.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="message_attachments",
                to="ai_layers.agent",
            ),
        ),
        migrations.AlterField(
            model_name="messageattachment",
            name="user",
            field=models.ForeignKey(
                blank=True,
                help_text="Owner (uploader or the user who ran the generating agent).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="message_attachments",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="messageattachment",
            name="visibility",
            field=models.CharField(
                choices=[
                    ("personal", "Personal"),
                    ("organization", "Organization"),
                    ("roles", "Roles"),
                    ("link", "Anyone with the link"),
                ],
                db_index=True,
                default="personal",
                help_text=(
                    "Who can list/read this attachment: me, organization, selected roles, "
                    "or anyone with the id/link."
                ),
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="messageattachment",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                help_text="Organization scope when visibility is organization, roles, or link.",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="message_attachments",
                to="authenticate.organization",
            ),
        ),
        migrations.AddField(
            model_name="messageattachment",
            name="allowed_roles",
            field=models.ManyToManyField(
                blank=True,
                help_text=(
                    "When visibility is roles, users with any of these roles "
                    "(or the org owner) can access."
                ),
                related_name="allowed_message_attachments",
                to="authenticate.role",
            ),
        ),
        migrations.RunPython(backfill_personal_visibility, noop_reverse),
    ]
