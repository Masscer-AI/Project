import logging

from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Agent, AgentKind, LanguageModel, RoleAgentAssignment
from api.authenticate.models import UserProfile
from api.rag.models import Collection
from api.consumption.models import Currency, Wallet

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def user_created(sender, instance, created, **kwargs):
    if created:
        Agent.objects.create(
            name=f"{instance.username}'s Agent", salute="Welcome!", user=instance
        )
        logger.debug("New user created, creating agent for user: %s", instance.username)

    _, created = UserProfile.objects.get_or_create(user=instance)
    if created:
        logger.debug("New user profile created for user: %s", instance.username)

    user_wallet, created = Wallet.objects.get_or_create(
        user=instance, unit=Currency.objects.get(name="Compute Unit")
    )
    if created:
        user_wallet.balance = 5000
        user_wallet.save()
        logger.debug("New wallet created for user: %s", instance.username)


@receiver(pre_delete, sender=LanguageModel)
def reassign_agents_on_llm_delete(sender, instance, **kwargs):
    """Migrate agents off a LanguageModel before it is deleted."""
    affected = Agent.objects.filter(llm=instance)
    if not affected.exists():
        return

    replacement = (
        LanguageModel.objects.filter(provider=instance.provider)
        .exclude(pk=instance.pk)
        .first()
    ) or LanguageModel.objects.exclude(pk=instance.pk).first()

    if replacement:
        count = affected.update(llm=replacement, model_slug=replacement.slug)
        logger.info(
            "Reassigned %s agent(s) from '%s' to '%s'.",
            count,
            instance.name,
            replacement.name,
        )
    else:
        logger.warning(
            "Deleting '%s' but no replacement model found — affected agents will have llm=NULL.",
            instance.name,
        )


@receiver(post_save, sender=Agent)
def agent_created(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.agent_kind == AgentKind.PLATFORM_ASSISTANT:
        return
    username = getattr(instance.user, "username", None) or "unknown"
    logger.debug("New agent created for user: %s", username)
    collection, collection_created = Collection.get_or_create_agent_collection(instance)
    if collection_created:
        logger.debug("New collection created for agent: %s", instance.id)
    else:
        logger.debug(
            "Collection already exists for agent: %s (collection=%s)",
            instance.id,
            collection.id,
        )


@receiver(post_save, sender=RoleAgentAssignment)
@receiver(post_delete, sender=RoleAgentAssignment)
def role_agent_assignment_changed(sender, instance, **kwargs):
    """
    If role-based access mapping changes, bump agent list cache for org members
    so visibility updates immediately.
    """
    try:
        from api.ai_layers.cache_utils import bump_agent_list_version_for_org_members
    except Exception:
        return

    agent = getattr(instance, "agent", None)
    org = getattr(agent, "organization", None) if agent else None
    if org:
        bump_agent_list_version_for_org_members(org)
