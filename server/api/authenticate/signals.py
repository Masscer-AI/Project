import logging

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connection, transaction
from django.db.models.signals import post_save, post_delete, pre_delete
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

    if org.owner_id:
        _invalidate_ff_cache_for_user(org.owner_id)

    member_user_ids = (
        UserProfile.objects.filter(organization_id=organization_id)
        .values_list("user_id", flat=True)
    )
    for uid in member_user_ids:
        _invalidate_ff_cache_for_user(uid)

@receiver(pre_delete, sender=Organization)
def delete_organization_members(sender, instance, **kwargs):
    """Delete every user whose profile belongs to this organization.

    The owner is excluded from the bulk delete because Organization.owner is
    on_delete=CASCADE — deleting them mid-org-deletion triggers a second
    cascade on the same org and causes a DB constraint error. The owner user
    is deleted last, after the org row itself is gone.
    """
    member_user_ids = list(
        UserProfile.objects.filter(organization=instance)
        .exclude(user_id=instance.owner_id)
        .values_list("user_id", flat=True)
    )
    if member_user_ids:
        deleted, _ = User.objects.filter(id__in=member_user_ids).delete()
        logger.info("Deleted %d member users for org %s", deleted, instance.id)

    owner_id = instance.owner_id

    def _delete_owner():
        User.objects.filter(id=owner_id).delete()
        logger.info("Deleted owner user %s after org %s was removed", owner_id, instance.id)

    if connection.in_atomic_block:
        transaction.on_commit(_delete_owner)
    else:
        _delete_owner()

@receiver(post_save, sender=Organization)
def create_credentials_manager(sender, instance, created, **kwargs):
    if created:
        CredentialsManager.objects.create(organization=instance)

@receiver(post_save, sender=Organization)
def provision_platform_assistant_on_org_create(sender, instance, created, **kwargs):
    if not created:
        return

    def _provision():
        try:
            from api.ai_layers.platform_assistant import provision_platform_assistant

            agent, was_created = provision_platform_assistant(instance)
            logger.info(
                "Platform assistant for org %s: agent=%s created=%s",
                instance.id,
                agent.id,
                was_created,
            )
        except Exception:
            logger.exception(
                "Failed to provision platform assistant for org %s", instance.id
            )

    if connection.in_atomic_block:
        transaction.on_commit(_provision)
    else:
        _provision()

@receiver(post_save, sender=Organization)
def create_free_trial_subscription(sender, instance, created, **kwargs):
    """Auto-enroll a new organization in the Free Trial plan."""
    if not created:
        return

    def _setup():
        try:
            from api.payments.models import Subscription, SubscriptionPlan
            from api.consumption.models import Currency, OrganizationWalletTransaction
            from api.payments.billing_helpers import recharge_org_wallet_compute_units
            from django.utils import timezone as tz
            import datetime

            plan = SubscriptionPlan.objects.filter(slug="free_trial").first()
            if plan is None:
                logger.warning(
                    "free_trial SubscriptionPlan does not exist yet — skipping auto-enrollment for org %s",
                    instance.id,
                )
                return

            end_date = tz.now() + datetime.timedelta(days=plan.duration_days or 3)
            subscription = Subscription.objects.create(
                organization=instance,
                plan=plan,
                status="trial",
                payment_method="manual",
                end_date=end_date,
            )
            logger.info("Created free trial subscription %s for org %s", subscription.id, instance.id)

            currency = Currency.objects.filter(name="Compute Unit").first()
            if currency is None:
                logger.warning("Compute Unit currency not found — org wallet not seeded for org %s", instance.id)
                return

            from decimal import Decimal
            credits_usd = plan.credits_limit_usd or Decimal("0")
            compute_units = credits_usd * Decimal(currency.one_usd_is)

            recharge_org_wallet_compute_units(
                instance,
                compute_units,
                bucket=OrganizationWalletTransaction.BUCKET_SUBSCRIPTION,
                reason=OrganizationWalletTransaction.REASON_TRIAL_SEED,
                subscription=subscription,
            )

            logger.info(
                "Seeded org wallet with %s compute units for org %s",
                compute_units,
                instance.id,
            )

        except Exception:
            logger.exception("Failed to set up free trial for org %s", instance.id)

    if connection.in_atomic_block:
        transaction.on_commit(_setup)
    else:
        _setup()

@receiver(post_save, sender=FeatureFlag)
@receiver(post_delete, sender=FeatureFlag)
def invalidate_ff_names_on_change(sender, instance, **kwargs):
    _invalidate_ff_names_cache()

@receiver(post_save, sender=FeatureFlagAssignment)
@receiver(post_delete, sender=FeatureFlagAssignment)
def invalidate_ff_cache_on_assignment_change(sender, instance, **kwargs):
    if instance.user_id:
        _invalidate_ff_cache_for_user(instance.user_id)
    elif instance.organization_id:
        _invalidate_ff_cache_for_org_members(instance.organization_id)

@receiver(post_save, sender=Role)
def invalidate_ff_cache_on_role_change(sender, instance, **kwargs):
    user_ids = (
        RoleAssignment.objects.filter(role=instance)
        .values_list("user_id", flat=True)
        .distinct()
    )
    for uid in user_ids:
        _invalidate_ff_cache_for_user(uid)

@receiver(post_save, sender=RoleAssignment)
@receiver(post_delete, sender=RoleAssignment)
def invalidate_ff_cache_on_role_assignment_change(sender, instance, **kwargs):
    uid = getattr(instance, "user_id", None)
    org_id = getattr(instance, "organization_id", None)
    if uid:
        _invalidate_ff_cache_for_user(uid)
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
                pass
