from django.db import models
from django.contrib.auth.models import User
from api.ai_layers.models import Agent


class WSNumber(models.Model):
    organization = models.ForeignKey(
        "authenticate.Organization",
        on_delete=models.CASCADE,
        related_name="whatsapp_numbers",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="whatsapp_numbers",
    )
    agent = models.ForeignKey(
        Agent, on_delete=models.CASCADE, related_name="whatsapp_numbers"
    )
    name = models.CharField(max_length=100, null=True, blank=True)
    capabilities = models.JSONField(default=list, blank=True)
    number = models.CharField(max_length=15)
    platform_id = models.CharField(max_length=50, null=True, blank=True)
    waba_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="WhatsApp Business Account id (optional). Used for admin webhook setup; "
        "left blank it is resolved from platform_id via Graph when possible.",
    )
    verified = models.BooleanField(default=False)
    certicate_b64 = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"WSNumber({self.name} - {self.number})"

    def send_message(self, conversation, message: str):
        from api.messaging.models import Message

        from .actions import send_message as send_message_action

        if not conversation.whatsapp_user_number:
            raise ValueError("Conversation is not linked to a WhatsApp user number")
        reply_message_platform_id = conversation.whatsapp_last_inbound_wamid
        wamid = send_message_action(
            self.platform_id,
            conversation.whatsapp_user_number,
            message,
            reply_message_platform_id,
        )
        Message.objects.create(
            conversation=conversation,
            type="assistant",
            text=message,
            metadata={"whatsapp_wamid": wamid} if wamid else {},
        )
