from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Message
from api.utils.color_printer import printer
from api.consumption.tasks import async_register_llm_interaction
from api.messaging.tasks import get_user_organization
from api.authenticate.services import FeatureFlagService


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
            if organization:
                enabled, _ = FeatureFlagService.is_feature_enabled(
                    "conversation-analysis", organization=organization, user=conversation.user
                )
            else:
                enabled = False
            if enabled:
                # Solo marcar si no está ya marcada (evitar updates innecesarios)
                if not conversation.pending_analysis:
                    conversation.pending_analysis = True
                    conversation.save(update_fields=['pending_analysis'])
                    printer.info(f"Conversation {conversation.id} marked for analysis")

    except Exception as e:
        printer.error(f"Error in post_save message signal: {str(e)}")
