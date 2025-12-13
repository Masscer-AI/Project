# Generated manually - Data migration from OrganizationMember to UserProfile

from django.db import migrations


def migrate_organization_members(apps, schema_editor):
    """
    Migrate data from OrganizationMember to UserProfile.organization.
    For users with multiple organizations, use the first one (by created_at).
    """
    OrganizationMember = apps.get_model('authenticate', 'OrganizationMember')
    UserProfile = apps.get_model('authenticate', 'UserProfile')
    
    # Get all unique users from OrganizationMember
    for member in OrganizationMember.objects.select_related('user', 'organization').order_by('user_id', 'created_at'):
        try:
            # Get or create UserProfile for this user
            profile, created = UserProfile.objects.get_or_create(user=member.user)
            
            # If the profile doesn't have an organization yet, assign it
            # (This handles the case where a user has multiple organizations - we take the first one)
            if not profile.organization:
                profile.organization = member.organization
                profile.save()
        except Exception as e:
            # Log error but continue migration
            print(f"Error migrating organization member for user {member.user_id}: {e}")


def reverse_migration(apps, schema_editor):
    """
    Reverse migration: Create OrganizationMember records from UserProfile.organization
    """
    OrganizationMember = apps.get_model('authenticate', 'OrganizationMember')
    UserProfile = apps.get_model('authenticate', 'UserProfile')
    
    # Create OrganizationMember for each UserProfile with an organization
    for profile in UserProfile.objects.filter(organization__isnull=False).select_related('user', 'organization'):
        OrganizationMember.objects.get_or_create(
            user=profile.user,
            organization=profile.organization
        )


class Migration(migrations.Migration):

    dependencies = [
        ('authenticate', '0010_add_organization_to_userprofile'),
    ]

    operations = [
        migrations.RunPython(migrate_organization_members, reverse_migration),
    ]

