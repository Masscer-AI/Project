from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authenticate", "0023_organizationmanagementproxy"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="subdomain",
            field=models.SlugField(
                blank=True,
                help_text="Claimed tenant subdomain (e.g. acme for acme.masscer.ai)",
                max_length=63,
                null=True,
                unique=True,
            ),
        ),
    ]
