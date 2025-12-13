# Generated manually - Data migration from OrganizationMember to UserProfile

from django.db import migrations


def migrate_organization_members(apps, schema_editor):
    """
    Migrate data from OrganizationMember to UserProfile.organization.
    For users with multiple organizations, use the first one (by created_at).
    """
    OrganizationMember = apps.get_model('authenticate', 'OrganizationMember')
    UserProfile = apps.get_model('authenticate', 'UserProfile')
    
    errors = []
    last_user_id = None
    
    for member in OrganizationMember.objects.select_related('user', 'organization').order_by('user_id', 'created_at'):
        # Skip subsequent memberships for the same user (we only assign the first org)
        if member.user_id == last_user_id:
            continue
        last_user_id = member.user_id
        
        try:
            profile, _created = UserProfile.objects.get_or_create(user=member.user)
            if not profile.organization:
                profile.organization = member.organization
                profile.save(update_fields=['organization'])
        except Exception as e:
            errors.append(f"Error migrating organization member for user {member.user_id}: {e}")
    
    if errors:
        raise RuntimeError(f"Migration failed with {len(errors)} errors:\n" + "\n".join(errors))


def reverse_migration(apps, schema_editor):
    """
    Reverse migration: Create OrganizationMember records from UserProfile.organization
    """
    OrganizationMember = apps.get_model('authenticate', 'OrganizationMember')
    UserProfile = apps.get_model('authenticate', 'UserProfile')
    
    errors = []
    
    for profile in UserProfile.objects.filter(organization__isnull=False).select_related('user', 'organization'):
        try:
            OrganizationMember.objects.get_or_create(
                user=profile.user,
                organization=profile.organization
            )
        except Exception as e:
            errors.append(f"Error creating OrganizationMember for user {profile.user_id}: {e}")
    
    if errors:
        raise RuntimeError(f"Reverse migration failed with {len(errors)} errors:\n" + "\n".join(errors))


class Migration(migrations.Migration):

    dependencies = [
        ('authenticate', '0010_add_organization_to_userprofile'),
    ]

    operations = [
        migrations.RunPython(migrate_organization_members, reverse_migration),
    ]

