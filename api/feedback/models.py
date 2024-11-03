from django.db import models
from api.messaging.models import Conversation, Message
from api.authenticate.models import User


class ReactionTemplate(models.Model):

    REACTION_TYPES = [
        ("system", "System"),
        ("user", "User"),
    ]
    RENDER_AS = [
        ("html", "HTML"),
        ("text", "Text"),
    ]
    name = models.CharField(max_length=25)
    emoji = models.TextField()
    emoji_type = models.CharField(max_length=25, choices=RENDER_AS, default="text")
    description = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    type = models.CharField(max_length=25, choices=REACTION_TYPES, default="system")
    is_public = models.BooleanField(default=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.name



class Reaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, null=True, blank=True
    )
    template = models.ForeignKey(
        ReactionTemplate, on_delete=models.SET_NULL, null=True, blank=True
    )
    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
