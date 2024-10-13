from django.db import models
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator
from api.providers.models import AIProvider

DEFAULT_CHARACTER = """
You are an useful assistant.
"""

DEFAULT_SYSTEM_PROMPT = """
{{act_as}}

The following context may be useful for your task:
```
{{context}}
```
"""


class LanguageModel(models.Model):
    provider = models.ForeignKey(AIProvider, on_delete=models.CASCADE)
    slug = models.CharField(max_length=100, unique=True, blank=True)
    name = models.CharField(max_length=100)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.provider.name})"


class Agent(models.Model):

    MODEL_PROVIDER_CHOICES = [
        ("openai", "OpenAI"),
        ("ollama", "Ollama"),
        ("anthropic", "Anthropic"),
    ]

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    model_slug = models.CharField(
        max_length=100, default="gpt-4o-mini", null=True, blank=True
    )

    model_provider = models.CharField(
        max_length=20, choices=MODEL_PROVIDER_CHOICES, default="openai"
    )
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

    def format_prompt(self, context: str = ""):
        formatted = self.system_prompt.replace("{{act_as}}", self.act_as).replace(
            "{{context}}", context
        )
        return formatted


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
