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
    balance = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    unit = models.ForeignKey(Currency, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"<Wallet user={self.user.username} balance={self.balance} />"

    def use_balance(self, amount: Decimal):
        self.balance -= amount
        self.save()
        if self.balance < 0:
            self.balance = 0
            self.save()
            return False
        return True


class Consumption(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    wallet = models.ForeignKey(Wallet, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=20, decimal_places=8, default=0.1)
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


class OrganizationWallet(models.Model):
    """Org wallet: subscription credits (forfeited when subscription ends) vs purchased (retained)."""

    organization = models.OneToOneField(
        "authenticate.Organization",
        on_delete=models.CASCADE,
        related_name="wallet",
    )
    subscription_balance = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=0,
        validators=[MinValueValidator(Decimal("0"))],
    )
    purchased_balance = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=0,
        validators=[MinValueValidator(Decimal("0"))],
    )
    unit = models.ForeignKey(Currency, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Organization wallet"
        verbose_name_plural = "Organization wallets"

    def __str__(self):
        return (
            f"<OrganizationWallet org={self.organization.name} "
            f"sub={self.subscription_balance} purchased={self.purchased_balance} />"
        )

    @property
    def total_balance(self) -> Decimal:
        return self.subscription_balance + self.purchased_balance


class OrganizationWalletTransaction(models.Model):
    """Audit trail for org wallet subscription vs purchased bucket changes."""

    BUCKET_SUBSCRIPTION = "subscription"
    BUCKET_PURCHASED = "purchased"
    BUCKET_CHOICES = [
        (BUCKET_SUBSCRIPTION, "Subscription"),
        (BUCKET_PURCHASED, "Purchased"),
    ]

    REASON_TRIAL_SEED = "trial_seed"
    REASON_STRIPE_CHECKOUT = "stripe_checkout"
    REASON_STRIPE_RENEW = "stripe_renew"
    REASON_STRIPE_TOPUP = "stripe_topup"
    REASON_ADMIN_RECHARGE = "admin_recharge"
    REASON_ADMIN_MANUAL_SUB = "admin_manual_sub"
    REASON_FORFEIT_EXPIRY = "forfeit_expiry"
    REASON_MIGRATION = "migration"
    REASON_CHOICES = [
        (REASON_TRIAL_SEED, "Trial seed"),
        (REASON_STRIPE_CHECKOUT, "Stripe checkout"),
        (REASON_STRIPE_RENEW, "Stripe renew"),
        (REASON_STRIPE_TOPUP, "Stripe top-up"),
        (REASON_ADMIN_RECHARGE, "Admin wallet recharge"),
        (REASON_ADMIN_MANUAL_SUB, "Admin manual subscription"),
        (REASON_FORFEIT_EXPIRY, "Forfeit on subscription end"),
        (REASON_MIGRATION, "Data migration"),
    ]

    organization = models.ForeignKey(
        "authenticate.Organization",
        on_delete=models.CASCADE,
        related_name="wallet_transactions",
    )
    bucket = models.CharField(max_length=20, choices=BUCKET_CHOICES)
    delta = models.DecimalField(max_digits=20, decimal_places=8)
    reason = models.CharField(max_length=32, choices=REASON_CHOICES)
    subscription = models.ForeignKey(
        "payments.Subscription",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wallet_transactions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "-created_at"]),
        ]

    def __str__(self):
        return f"<OrgWalletTx org={self.organization_id} {self.bucket} {self.delta} {self.reason}>"
