from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Conversation, Message
from api.preferences.models import UserTags
from api.utils.color_printer import printer
from api.preferences.actions import clean_unused_tags
from api.consumption.actions import register_llm_interaction
from api.consumption.tasks import async_register_llm_interaction


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


@receiver(post_save, sender=Message)
def message_post_save(sender, instance, **kwargs):
    try:
        if instance.type == "assistant":
            # printer.info("Assistant message detected")
            for version in instance.versions:

                model_slug = version["usage"]["model_slug"]

                input_tokens = version["usage"]["prompt_tokens"]
                output_tokens = version["usage"]["completion_tokens"]

                if not input_tokens or not output_tokens:
                    printer.error("No tokens found!")
                    return

                if not instance.conversation.user:
                    printer.error("No user found!")
                    return

                async_register_llm_interaction.delay(
                    instance.conversation.user.id,
                    input_tokens,
                    output_tokens,
                    model_slug,
                )

    except Exception as e:
        printer.error(f"Error in post_save message signal: {str(e)}")
