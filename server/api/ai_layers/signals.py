from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Agent, RoleAgentAssignment
from api.authenticate.models import UserProfile
from api.rag.models import Collection
from api.consumption.models import Currency, Wallet


@receiver(post_save, sender=User)
def user_created(sender, instance, created, **kwargs):
    if created:
        Agent.objects.create(
            name=f"{instance.username}'s Agent", salute="Welcome!", user=instance
        )
        print(f"New user created, creating agent for user: {instance.username}")

    _, created = UserProfile.objects.get_or_create(user=instance)
    if created:
        print(f"New user profile created for user: {instance.username}")

    user_wallet, created = Wallet.objects.get_or_create(
        user=instance, unit=Currency.objects.get(name="Compute Unit")
    )
    if created:
        user_wallet.balance = 5000
        user_wallet.save()
        print(f"New wallet created for user: {instance.username}")


@receiver(post_save, sender=Agent)
def agent_created(sender, instance, created, **kwargs):
    if created:
        print(f"New agent created for user: {instance.user.username}")
        collection, collection_created = Collection.get_or_create_agent_collection(instance)
        if collection_created:
            print(f"New collection created for agent: {instance.id}")
        else:
            print(f"Collection already exists for agent: {instance.id} (collection={collection.id})")


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
