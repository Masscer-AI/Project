from django.db import models
from django.contrib.auth.models import User


class UserPreferences(models.Model):
    THEME_CHOICES = [
        ("system", "System"),
        ("light", "Light"),
        ("dark", "Dark"),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="preferences"
    )
    max_memory_messages = models.IntegerField(default=20)
    autoscroll = models.BooleanField(default=False)
    autoplay = models.BooleanField(default=False)
    background_image_source = models.TextField(blank=True)
    theme = models.CharField(max_length=50, default="system", choices=THEME_CHOICES)

    def __str__(self):
        return f"UserPreferences for {self.user.username}: max_memory_messages={self.max_memory_messages}, autoscroll={self.autoscroll}, autoplay={self.autoplay}"
