from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Conversation, Message
from api.preferences.models import UserTags
from api.utils.color_printer import printer
from api.preferences.actions import clean_unused_tags
from api.consumption.actions import register_llm_interaction
from api.consumption.tasks import async_register_llm_interaction
from api.messaging.tasks import get_user_organization
from api.authenticate.services import FeatureFlagService


@receiver(post_save, sender=Conversation)
def conversation_post_save(sender, instance, **kwargs):
    try:
        # Verificar que la conversación tenga un usuario antes de procesar tags
        if not instance.user:
            return
        
        # Tags ahora es JSONField con lista de IDs
        tag_ids = instance.tags if isinstance(instance.tags, list) else []
        
        if len(tag_ids) == 0:
            return

        user_tags = UserTags.objects.filter(user=instance.user).first()
        if not user_tags:
            user_tags = UserTags.objects.create(user=instance.user)

        # Obtener los títulos de las tags desde la base de datos
        from .models import Tag
        tags = Tag.objects.filter(id__in=tag_ids)
        
        # Agregar los títulos de las tags al UserTags
        for tag in tags:
            user_tags.add_tag(tag.title)

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
        
        # Marcar conversación como pendiente de análisis si corresponde
        conversation = instance.conversation
        if conversation.user:
            organization = get_user_organization(conversation.user)
            if organization and FeatureFlagService.is_feature_enabled(
                "conversation-analysis", organization=organization, user=conversation.user
            ):
                # Solo marcar si no está ya marcada (evitar updates innecesarios)
                if not conversation.pending_analysis:
                    conversation.pending_analysis = True
                    conversation.save(update_fields=['pending_analysis'])
                    printer.info(f"Conversation {conversation.id} marked for analysis")

    except Exception as e:
        printer.error(f"Error in post_save message signal: {str(e)}")
