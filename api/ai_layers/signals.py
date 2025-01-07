from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Agent
from api.authenticate.models import UserProfile
from api.rag.models import Collection


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


@receiver(post_save, sender=Agent)
def agent_created(sender, instance, created, **kwargs):
    if created:
        print(f"New agent created for user: {instance.user.username}")
        collection = Collection.objects.create(agent=instance, user=instance.user)
        print(f"New collection created for agent: {instance.id}")
        
