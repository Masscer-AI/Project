# Generated manually for WhatsApp number access scope

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authenticate", "0026_userprofile__phone_numbers"),
        ("whatsapp", "0016_wscontact"),
    ]

    operations = [
        migrations.AddField(
            model_name="wsnumber",
            name="access_mode",
            field=models.CharField(
                choices=[
                    ("public", "Public"),
                    ("organization", "Organization"),
                    ("roles", "Roles"),
                    ("user", "Single user"),
                ],
                default="public",
                help_text="Who may message this WhatsApp line.",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="wsnumber",
            name="access_user",
            field=models.ForeignKey(
                blank=True,
                help_text="When access_mode=user, only this member may message (matched by profile phone).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="whatsapp_numbers_single_access",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="wsnumber",
            name="allowed_roles",
            field=models.ManyToManyField(
                blank=True,
                help_text="When access_mode=roles, members with any of these roles may message.",
                related_name="whatsapp_numbers_with_access",
                to="authenticate.role",
            ),
        ),
    ]
