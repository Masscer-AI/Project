from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Agent

@receiver(post_save, sender=User)
def user_created(sender, instance, created, **kwargs):
    if created:
        Agent.objects.create(
            name=f"{instance.username}'s Agent",
            salute="Welcome!",
            user=instance
        )
        print(f"New user created, creating agent for user: {instance.username}")

