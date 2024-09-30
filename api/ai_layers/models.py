from django.db import models
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator

DEFAULT_CHARACTER = """
You are an useful assistant.
"""

DEFAULT_SYSTEM_PROMPT = """
{{act_as}}

This context may be useful for your task
"""

class Agent(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    model_slug = models.CharField(max_length=100, null=True, blank=True)
    system_prompt = models.TextField(default=DEFAULT_SYSTEM_PROMPT)

    salute = models.TextField()
    act_as = models.TextField(
        default=DEFAULT_CHARACTER, help_text="How should the AI act?"
    )

    user = models.ForeignKey(
        "auth.User", on_delete=models.CASCADE, null=True, blank=True
    )

    is_public = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class ModelConfig(models.Model):
    temperature = models.FloatField(
        validators=[MinValueValidator(0.00), MaxValueValidator(2.00)]
    )
    max_tokens = models.IntegerField()
    top_p = models.FloatField(
        validators=[MinValueValidator(0.00), MaxValueValidator(1.00)]
    )
    frequency_penalty = models.FloatField(
        validators=[MinValueValidator(-2.00), MaxValueValidator(2.00)]
    )
    presence_penalty = models.FloatField(
        validators=[MinValueValidator(-2.00), MaxValueValidator(2.00)]
    )
