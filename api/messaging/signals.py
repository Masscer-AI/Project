# on conversation post save
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Conversation
from api.preferences.models import UserTags
from api.utils.color_printer import printer
from api.preferences.actions import clean_unused_tags


@receiver(post_save, sender=Conversation)
def conversation_post_save(sender, instance, **kwargs):
    try:

        if len(instance.tags) == 0:
            return

        user_tags = UserTags.objects.filter(user=instance.user).first()
        if not user_tags:
            user_tags = UserTags.objects.create(user=instance.user)

        for tag in instance.tags:
            user_tags.add_tag(tag)

        clean_unused_tags(instance.user.id)
        printer.info("User tags updated successfully")
    except Exception as e:
        printer.error(f"Error in post_save conversation signal: {str(e)}")
