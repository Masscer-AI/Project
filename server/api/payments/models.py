import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone as tz


class WinningRates(models.Model):
    name = models.CharField(max_length=255)
    llm_interaction_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=0.15,
    )
    image_generation_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=0.15,
    )
    video_generation_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=0.15,
    )
    speech_synthesis_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=0.15,
    )
    transcription_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=0.15,
    )
    document_generation_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=0.10,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class SubscriptionPlan(models.Model):
    PLAN_SLUGS = [
        ("free_trial", "Free Trial"),
        ("pay_as_you_go", "Pay As You Go"),
        ("organization", "Organization"),
    ]

    slug = models.CharField(max_length=50, unique=True, choices=PLAN_SLUGS)
    display_name = models.CharField(max_length=255)
    monthly_price_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    # USD credit budget included in this plan. Converted to compute units at wallet seed time.
    credits_limit_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Credit budget in USD included in this plan. Leave blank for unlimited.",
    )
    # How many days the plan lasts before requiring renewal. Null = ongoing.
    duration_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Days until plan expires. Leave blank for monthly recurring plans.",
    )
    # Whether the credits_limit can be overridden per subscription (e.g. pay_as_you_go).
    is_configurable = models.BooleanField(
        default=False,
        help_text="Allow per-subscription credit limit overrides.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.display_name


class Subscription(models.Model):
    STATUS_CHOICES = [
        ("trial", "Trial"),
        ("active", "Active"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled"),
        ("pending_payment", "Pending Payment"),
    ]

    PAYMENT_METHOD_CHOICES = [
        ("stripe", "Stripe"),
        ("manual", "Manual (Bank Transfer)"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "authenticate.Organization",
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="trial")
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default="manual",
    )
    # Stripe identifiers (populated only when payment_method=stripe)
    stripe_subscription_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_customer_id = models.CharField(max_length=255, null=True, blank=True)
    # Per-subscription USD credit override (used for pay_as_you_go)
    credits_limit_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Override the plan's default credit budget (in USD) for this subscription.",
    )
    start_date = models.DateTimeField(default=tz.now)
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this subscription expires. Null = active until cancelled.",
    )
    renewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"<Subscription org={self.organization.name} plan={self.plan.slug} status={self.status} />"

    def is_active(self) -> bool:
        if self.status not in ("trial", "active"):
            return False
        if self.end_date and tz.now() > self.end_date:
            return False
        return True

    def get_effective_credits_limit_usd(self):
        """Returns the USD credit budget in effect: subscription override > plan default."""
        if self.credits_limit_usd is not None:
            return self.credits_limit_usd
        return self.plan.credits_limit_usd


class SubscriptionPayment(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    METHOD_CHOICES = [
        ("stripe", "Stripe"),
        ("manual", "Manual (Bank Transfer)"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    amount_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default="manual")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    stripe_payment_intent_id = models.CharField(max_length=255, null=True, blank=True)
    # Billing team notes for manual payments
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"<SubscriptionPayment amount={self.amount_usd} status={self.status} />"
