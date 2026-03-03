# Generated manually - Delete OrganizationMember model

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('authenticate', '0011_migrate_organizationmember_to_userprofile'),
    ]

    operations = [
        migrations.DeleteModel(
            name='OrganizationMember',
        ),
    ]

