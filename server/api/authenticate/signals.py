import logging

from django.core.cache import cache
from django.db import connection, transaction
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

def _notify_invalidate_permissions_cache(user_id):
    """Tell connected clients to refetch team feature flags (Socket.IO via Redis)."""
    if not user_id:
        return
    try:
        from api.notify.actions import notify_user

        notify_user(user_id, "invalidate-permissions-cache", {})
    except Exception:
        logger.debug(
            "invalidate-permissions-cache notify failed for user %s",
            user_id,
            exc_info=True,
        )


def _invalidate_ff_cache_for_user(user_id):
    """Delete every feature-flag cache entry that belongs to *user_id*, then push WS refresh."""
    if not user_id:
        return

    def _run():
        cache.delete(f"ff_list_{user_id}")
        try:
            cache.delete_pattern(f"*ff_check_{user_id}_*")
        except Exception as exc:
            logger.warning(
                "Feature-flag cache delete_pattern failed for user %s: %s",
                user_id,
                exc,
            )
        logger.debug("Invalidated feature-flag cache for user %s", user_id)
        _notify_invalidate_permissions_cache(user_id)

    # Defer until DB commit so GET /feature-flags/ and the websocket refetch see updated roles.
    if connection.in_atomic_block:
        transaction.on_commit(_run)
    else:
        _run()


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
    uid = getattr(instance, "user_id", None)
    org_id = getattr(instance, "organization_id", None)
    if uid:
        _invalidate_ff_cache_for_user(uid)
        # Role changes can affect which organization agents are visible (role-restricted agents)
        if org_id:
            try:
                from api.ai_layers.cache_utils import bump_agent_list_version_for_user

                def _bump():
                    bump_agent_list_version_for_user(uid, str(org_id))

                if connection.in_atomic_block:
                    transaction.on_commit(_bump)
                else:
                    _bump()
            except Exception:
                # Keep feature-flag invalidation robust even if ai_layers isn't ready during migrations.
                pass
