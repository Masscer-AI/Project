from .models import CredentialsManager, Organization
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=Organization)
def create_credentials_manager(sender, instance, created, **kwargs):
    if created:
        CredentialsManager.objects.create(organization=instance)
