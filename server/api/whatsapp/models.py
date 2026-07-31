import re

from django.db import models
from django.contrib.auth.models import User
from api.ai_layers.models import Agent


def _normalize_phone(value: str) -> str:
    """Strip everything except digits. Accepts any formatting (+, spaces, dashes, parens)."""
    return re.sub(r"[^\d]", "", value or "")


class WSContact(models.Model):
    """
    Stable WhatsApp visitor identity for a business line.

    Created on first inbound with user=None. Org members with WhatsApp access
    may link the contact to an organization member (a user may own multiple
    contacts / phones on the same line).
    """

    ws_number = models.ForeignKey(
        "WSNumber",
        on_delete=models.CASCADE,
        related_name="contacts",
    )
    number = models.CharField(
        max_length=30,
        help_text="Visitor phone digits (country code included). Normalized on save.",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="whatsapp_contacts",
    )
    display_name = models.CharField(max_length=100, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["ws_number", "number"],
                name="uniq_wscontact_ws_number_number",
            ),
        ]

    def clean(self):
        self.number = _normalize_phone(self.number)

    def save(self, *args, **kwargs):
        self.number = _normalize_phone(self.number)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"WSContact({self.number} @ {self.ws_number_id})"


class WSNumber(models.Model):
    ACCESS_MODE_PUBLIC = "public"
    ACCESS_MODE_ORGANIZATION = "organization"
    ACCESS_MODE_ROLES = "roles"
    ACCESS_MODE_USER = "user"
    ACCESS_MODE_CHOICES = [
        (ACCESS_MODE_PUBLIC, "Public"),
        (ACCESS_MODE_ORGANIZATION, "Organization"),
        (ACCESS_MODE_ROLES, "Roles"),
        (ACCESS_MODE_USER, "Single user"),
    ]

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
    number = models.CharField(
        max_length=30,
        help_text="Phone number in any format — spaces, dashes, parentheses and + are stripped automatically.",
    )
    platform_id = models.CharField(max_length=50, null=True, blank=True)
    waba_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="WhatsApp Business Account id (optional). Used for admin webhook setup; "
        "left blank it is resolved from platform_id via Graph when possible.",
    )
    access_mode = models.CharField(
        max_length=20,
        choices=ACCESS_MODE_CHOICES,
        default=ACCESS_MODE_PUBLIC,
        help_text="Who may message this WhatsApp line.",
    )
    access_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="whatsapp_numbers_single_access",
        help_text="When access_mode=user, only this member may message (matched by profile phone).",
    )
    allowed_roles = models.ManyToManyField(
        "authenticate.Role",
        blank=True,
        related_name="whatsapp_numbers_with_access",
        help_text="When access_mode=roles, members with any of these roles may message.",
    )
    verified = models.BooleanField(default=False)
    certicate_b64 = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        self.number = _normalize_phone(self.number)

    def save(self, *args, **kwargs):
        self.number = _normalize_phone(self.number)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"WSNumber({self.name} - {self.number})"

    def send_message(
        self,
        conversation,
        message: str,
        *,
        reply_to_last_inbound: bool = True,
    ):
        from api.messaging.models import Message

        from .actions import send_message as send_message_action

        if not conversation.whatsapp_user_number:
            raise ValueError("Conversation is not linked to a WhatsApp user number")
        reply_message_platform_id = (
            conversation.whatsapp_last_inbound_wamid if reply_to_last_inbound else None
        )
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
