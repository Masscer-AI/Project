from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authenticate", "0026_userprofile__phone_numbers"),
    ]

    operations = [
        migrations.AddField(
            model_name="organizationinvite",
            name="intake",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Optional KYB intake: person_type, counterparty_role, relationship_status",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="intake",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Optional KYB intake copied from the organization invite",
            ),
        ),
    ]
