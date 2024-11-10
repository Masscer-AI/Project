from datetime import timedelta
import uuid
from django.db import models
from django.contrib.auth.models import User
from api.authenticate.models import PublishableToken


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    public_token = models.ForeignKey(
        PublishableToken, on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        if self.title:
            return self.title

        return f"Conversation({self.id})"

    def cut_from(self, message_id):
        # This must delete all messages after the given message id
        Message.objects.filter(conversation=self, id__gt=message_id).delete()

    def generate_title(self):
        if not self.title:
            from .tasks import async_generate_conversation_title

            async_generate_conversation_title.delay(self.id)

    def get_all_messages_context(self):
        return "\n".join(
            [f"{message.type}: {message.text}\n" for message in self.messages.all()]
        )


class Message(models.Model):
    TYPE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
    ]

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    text = models.TextField()
    attachments = models.JSONField(default=list, blank=True)
    versions = models.JSONField(default=list, blank=True)
    rag_sources = models.JSONField(default=list, blank=True)
    browse_sources = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.type}: {self.text[:50]}"


class SharedConversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    valid_until = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"SharedConversation({self.id})"

    def save(self, *args, **kwargs):\
        super().save(*args, **kwargs)
