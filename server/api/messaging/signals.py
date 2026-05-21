import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from api.authenticate.services import FeatureFlagService
from api.consumption.tasks import async_register_llm_interaction
from api.messaging.tasks import get_user_organization
from api.utils.color_printer import printer

from .models import Conversation, Message

logger = logging.getLogger(__name__)


def _resolve_billing_context(conversation: Conversation) -> tuple[int | None, int | None]:
    """
    Return (billing_user_id, organization_id) for consumption registration.

    Anonymous channels (widget/WhatsApp) have conversation.user=None; charge the org wallet
    using organization.owner_id when available.
    """
    organization_id = conversation.organization_id
    if conversation.user_id:
        if not organization_id and conversation.user:
            org = get_user_organization(conversation.user)
            organization_id = org.id if org else None
        return conversation.user_id, organization_id
    if organization_id:
        owner_id = conversation.organization.owner_id
        if owner_id:
            return owner_id, organization_id
    return None, organization_id


@receiver(post_save, sender=Message)
def message_post_save(sender, instance, **kwargs):
    try:
        if instance.type == "assistant":
            for version in instance.versions:
                usage = version.get("usage")
                if not usage:
                    continue

                model_slug = usage.get("model_slug")
                input_tokens = usage.get("prompt_tokens")
                output_tokens = usage.get("completion_tokens")

                if not input_tokens or not output_tokens:
                    continue

                billing_user_id, organization_id = _resolve_billing_context(
                    instance.conversation
                )
                if billing_user_id is None:
                    logger.warning(
                        "Skipping LLM usage billing: no billing user for conversation_id=%s "
                        "(organization_id=%s)",
                        instance.conversation_id,
                        organization_id,
                    )
                    continue

                async_register_llm_interaction.delay(
                    billing_user_id,
                    input_tokens,
                    output_tokens,
                    model_slug,
                    organization_id,
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
