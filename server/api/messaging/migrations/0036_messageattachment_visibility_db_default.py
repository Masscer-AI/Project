# Keep a Postgres DEFAULT so INSERTs that omit visibility (stale workers)
# still satisfy the NOT NULL constraint. Django 5 drops the DB default after
# AddField unless db_default is set.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("messaging", "0035_messageattachment_visibility_acl"),
    ]

    operations = [
        migrations.AlterField(
            model_name="messageattachment",
            name="visibility",
            field=models.CharField(
                choices=[
                    ("personal", "Personal"),
                    ("organization", "Organization"),
                    ("roles", "Roles"),
                    ("link", "Anyone with the link"),
                ],
                db_default="personal",
                db_index=True,
                default="personal",
                help_text=(
                    "Who can list/read this attachment: me, organization, selected roles, "
                    "or anyone with the id/link."
                ),
                max_length=20,
            ),
        ),
    ]
