from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authenticate', '0031_organizationinvite_welcome'),
        ('compliance', '0022_pldmatrixprofile_pldentity_matrix_profile_and_more'),
        ('esign', '0007_alter_signaturesigner_role'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='pldexpedient',
            name='unique_pld_expedient_per_org_entity',
        ),
        migrations.AddField(
            model_name='pldexpedient',
            name='completed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='pldexpedient',
            name='entity_snapshot',
            field=models.JSONField(blank=True, default=dict, help_text='Entity data and matrix score frozen when the run finished.'),
        ),
        migrations.AddField(
            model_name='pldexpedient',
            name='version',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddConstraint(
            model_name='pldexpedient',
            constraint=models.UniqueConstraint(fields=('entity', 'version'), name='unique_pld_expedient_version_per_entity'),
        ),
        migrations.AddConstraint(
            model_name='pldexpedient',
            constraint=models.UniqueConstraint(condition=models.Q(('status__in', ('signed', 'delivered')), _negated=True), fields=('entity',), name='unique_open_pld_expedient_per_entity'),
        ),
    ]
