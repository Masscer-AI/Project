from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.core.validators import MinValueValidator
from decimal import Decimal


class Currency(models.Model):
    """
    Default 1 dollar is 1000 compute units
    """

    name = models.CharField(max_length=255)
    one_usd_is = models.IntegerField(
        default=1000,
        help_text="1 dollar is THIS VALUE of compute units",
    )
    slug = models.SlugField(unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"<ComputeUnit name={self.name} one_usd_is={self.one_usd_is} />"

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=12, decimal_places=8, default=0)
    unit = models.ForeignKey(Currency, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"<Wallet user={self.user.username} balance={self.balance} />"

    def use_balance(self, amount: Decimal):
        if self.balance < amount:
            raise ValueError("Insufficient balance for this operation!")
        self.balance -= amount
        self.save()


class Consumption(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    wallet = models.ForeignKey(Wallet, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=8, default=0.1)
    is_for = models.CharField(
        max_length=255,
        choices=[
            ("llm_interaction", "LLM Interaction"),
            ("image_generation", "Image Generation"),
            ("video_generation", "Video Generation"),
            ("speech_synthesis", "Speech Synthesis"),
            ("transcription", "Transcription"),
            ("document_generation", "Document Generation"),
        ],
    )
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"<Consumption user={self.user.username} amount={self.amount} is_for={self.is_for} />"
