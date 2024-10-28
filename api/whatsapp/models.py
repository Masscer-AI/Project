from django.db import models
from django.contrib.auth.models import User
from api.ai_layers.models import Agent


class WSNumber(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="whatsapp_numbers"
    )
    agent = models.ForeignKey(
        Agent, on_delete=models.CASCADE, related_name="whatsapp_numbers"
    )
    name = models.CharField(max_length=100, null=True, blank=True)
    number = models.CharField(max_length=15)
    platform_id = models.CharField(max_length=50, null=True, blank=True)
    verified = models.BooleanField(default=False)
    certicate_b64 = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.number}"

    def send_message(
        self,
        conversation,
        message,
    ):

        from .actions import (
            send_message as send_message_action,
            save_ws_message,
        )

        reply_message_platform_id = conversation.get_last_valid_message_platform_id()
        send_message_action(
            self.platform_id,
            conversation.user_number,
            message,
            reply_message_platform_id,
        )
        # reply_platform_message_id = send_interactive_message(
        #     whatsapp_business_phone_number_id=self.platform_id,
        #     user_phone_number=conversation.user_number,
        #     header_text="some header",
        #     body_text=message,
        #     footer_text="some footer",
        #     buttons=[
        #         {"type": "reply", "reply": {"id": "change-button", "title": "Change"}},
        #         {"type": "reply", "reply": {"id": "cancel-button", "title": "Cancel"}},
        #     ],
        # )

        save_ws_message(
            conversation,
            message,
            "ASSISTANT",
            message_platform_id=reply_message_platform_id,
        )


class WSContact(models.Model):
    number = models.CharField(max_length=30)
    name = models.CharField(max_length=100)
    age = models.IntegerField(null=True, blank=True)
    gender = models.CharField(max_length=10, null=True, blank=True)

    language = models.CharField(max_length=10, null=True, blank=True)
    context = models.TextField(null=True, blank=True)
    collected_info = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"WSContact({self.name} - {self.number})"

    def update_info(self, context):
        self.collected_info = context
        self.save()
        return True


class WSConversation(models.Model):
    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("INACTIVE", "Inactive"),
    ]

    ai_number = models.ForeignKey(WSNumber, on_delete=models.CASCADE)
    user_number = models.CharField(max_length=30)
    user_contact = models.ForeignKey(
        WSContact, on_delete=models.CASCADE, null=True, blank=True
    )
    title = models.CharField(max_length=100, null=True, blank=True)
    sentiment = models.CharField(max_length=100, null=True, blank=True)
    summary = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default="ACTIVE")

    def __str__(self):
        return f"WSConversation(from={self.ai_number.number}, to={self.user_number})"

    def get_context(self, n=10):
        """
        Returns a string containing the latest n messages formatted in an understandable way
        from the first to the last one (ordered by created_at).
        """
        # Get the latest n messages from the conversation
        messages = self.messages.order_by("created_at")[:n]

        # Create a list to hold formatted message strings
        formatted_messages = []

        for message in messages:
            formatted_messages.append(f"{message.message_type}: {message.content}")

        # Join the formatted messages into a single string
        return "\n".join(formatted_messages)

    def get_user_info(self):
        if self.user_contact:
            return self.user_contact.collected_info
        return None

    def update_user_info(self):
        context = self.get_context()
        if self.user_contact:
            self.user_contact.update_info(context)
            return True

        else:
            contact = WSContact.objects.create(
                number=self.user_number,
                name=self.title,
            )
            self.user_contact = contact
            self.save()
            contact.update_info(context)
            return True

    def get_last_valid_message_platform_id(self):
        """
        Returns the last message_platform_id from an user that is not None.
        """
        messages = self.messages.order_by("created_at")
        for message in messages:
            if message.message_platform_id and message.message_type == "USER":
                return message.message_platform_id
        return None


class WSMessage(models.Model):
    MESSAGE_TYPE_CHOICES = [
        ("USER", "User"),
        ("ASSISTANT", "Assistant"),
    ]

    conversation = models.ForeignKey(
        WSConversation, on_delete=models.CASCADE, related_name="messages"
    )
    content = models.TextField()
    message_platform_id = models.CharField(max_length=255, null=True, blank=True)
    collected_info = models.TextField(null=True, blank=True)
    reaction = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    message_type = models.CharField(max_length=9, choices=MESSAGE_TYPE_CHOICES)

    def __str__(self):
        return f"Message({self.message_type}): {self.content[:20]}..."
