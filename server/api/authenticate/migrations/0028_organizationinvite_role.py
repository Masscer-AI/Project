from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("authenticate", "0027_invite_and_profile_intake"),
    ]

    operations = [
        migrations.AddField(
            model_name="organizationinvite",
            name="role",
            field=models.ForeignKey(
                blank=True,
                help_text="Role assigned when the invite is accepted.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="organization_invites",
                to="authenticate.role",
            ),
        ),
    ]
