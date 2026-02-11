import logging

from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import (
    CredentialsManager,
    Organization,
    FeatureFlag,
    FeatureFlagAssignment,
    Role,
    RoleAssignment,
    UserProfile,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers – feature-flag cache invalidation
# ---------------------------------------------------------------------------

def _invalidate_ff_cache_for_user(user_id):
    """Delete every feature-flag cache entry that belongs to *user_id*."""
    cache.delete(f"ff_list_{user_id}")
    # ff_check keys follow the pattern ff_check_{user_id}_{flag_name}
    cache.delete_pattern(f"*ff_check_{user_id}_*")
    logger.debug("Invalidated feature-flag cache for user %s", user_id)


def _invalidate_ff_names_cache():
    """Delete the global feature-flag names cache."""
    cache.delete("feature_flag_names")


def _invalidate_ff_cache_for_org_members(organization_id):
    """Invalidate feature-flag caches for every member (and owner) of an org."""
    try:
        org = Organization.objects.get(id=organization_id)
    except Organization.DoesNotExist:
        return

    # Owner
    if org.owner_id:
        _invalidate_ff_cache_for_user(org.owner_id)

    # Members (users whose profile points to this org)
    member_user_ids = (
        UserProfile.objects.filter(organization_id=organization_id)
        .values_list("user_id", flat=True)
    )
    for uid in member_user_ids:
        _invalidate_ff_cache_for_user(uid)


# ---------------------------------------------------------------------------
# Organization – create credentials manager
# ---------------------------------------------------------------------------

@receiver(post_save, sender=Organization)
def create_credentials_manager(sender, instance, created, **kwargs):
    if created:
        CredentialsManager.objects.create(organization=instance)


# ---------------------------------------------------------------------------
# FeatureFlag – invalidate names cache on any change
# ---------------------------------------------------------------------------

@receiver(post_save, sender=FeatureFlag)
@receiver(post_delete, sender=FeatureFlag)
def invalidate_ff_names_on_change(sender, instance, **kwargs):
    _invalidate_ff_names_cache()


# ---------------------------------------------------------------------------
# FeatureFlagAssignment – invalidate per-user (or per-org-members) caches
# ---------------------------------------------------------------------------

@receiver(post_save, sender=FeatureFlagAssignment)
@receiver(post_delete, sender=FeatureFlagAssignment)
def invalidate_ff_cache_on_assignment_change(sender, instance, **kwargs):
    if instance.user_id:
        # User-level assignment → only that user is affected
        _invalidate_ff_cache_for_user(instance.user_id)
    elif instance.organization_id:
        # Org-level assignment → every member of the org is affected
        _invalidate_ff_cache_for_org_members(instance.organization_id)


# ---------------------------------------------------------------------------
# Role – capabilities may have changed → invalidate users who hold this role
# ---------------------------------------------------------------------------

@receiver(post_save, sender=Role)
def invalidate_ff_cache_on_role_change(sender, instance, **kwargs):
    user_ids = (
        RoleAssignment.objects.filter(role=instance)
        .values_list("user_id", flat=True)
        .distinct()
    )
    for uid in user_ids:
        _invalidate_ff_cache_for_user(uid)


# ---------------------------------------------------------------------------
# RoleAssignment – user gained / lost a role → invalidate that user
# ---------------------------------------------------------------------------

@receiver(post_save, sender=RoleAssignment)
@receiver(post_delete, sender=RoleAssignment)
def invalidate_ff_cache_on_role_assignment_change(sender, instance, **kwargs):
    if instance.user_id:
        _invalidate_ff_cache_for_user(instance.user_id)
