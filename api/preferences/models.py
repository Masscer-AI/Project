from django.db import models
from django.contrib.auth.models import User


class UserPreferences(models.Model):
    THEME_CHOICES = [
        ("system", "System"),
        ("light", "Light"),
        ("dark", "Dark"),
    ]
    MULTIAGENTIC_CHOICES = [
        ("isolated", "Isolated"),
        ("grupal", "Grupal"),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="preferences"
    )
    max_memory_messages = models.IntegerField(default=20)
    autoscroll = models.BooleanField(default=False)
    autoplay = models.BooleanField(default=False)
    background_image_source = models.TextField(blank=True)
    background_image_opacity = models.FloatField(default=0.5)
    theme = models.CharField(max_length=50, default="system", choices=THEME_CHOICES)
    multiagentic_modality = models.CharField(
        max_length=50, default="isolated", choices=MULTIAGENTIC_CHOICES
    )

    def __str__(self):
        return f"UserPreferences for {self.user.username}: max_memory_messages={self.max_memory_messages}, autoscroll={self.autoscroll}, autoplay={self.autoplay}"


class UserTags(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tags")
    tags = models.JSONField(default=list)

    def __str__(self):
        return f"UserTags for {self.user.username}: {self.tags}"

    def add_tag(self, tag: str):
        if tag not in self.tags:
            self.tags.append(tag)
            self.save()

    def remove_tag(self, tag: str):
        if tag in self.tags:
            self.tags.remove(tag)
            self.save()


class UserVoices(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="voices")
    voices = models.JSONField(default=list)

    def __str__(self):
        return f"UserVoices for {self.user.username}"


class WebPage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="web_pages")
    url = models.URLField(max_length=2048)
    title = models.CharField(max_length=255, blank=True)
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "url")
        ordering = ["-is_pinned", "-created_at"]

    def __str__(self):
        return f"WebPage for {self.user.username}: {self.url}"
