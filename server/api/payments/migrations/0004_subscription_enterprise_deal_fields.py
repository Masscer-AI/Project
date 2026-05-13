# Generated manually for enterprise / admin-managed subscription metadata

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0003_remove_subscription_credits_limit_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscription",
            name="billing_interval",
            field=models.CharField(
                choices=[
                    ("monthly", "Monthly"),
                    ("quarterly", "Quarterly"),
                    ("yearly", "Yearly"),
                    ("one_time", "One-time"),
                    ("custom", "Custom"),
                ],
                default="monthly",
                help_text="Billing cadence for enterprise deals (informational unless enforced elsewhere).",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="subscription",
            name="contract_price_usd",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Negotiated contract price in USD for this subscription (overrides plan list price for display).",
                max_digits=10,
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
        migrations.AddField(
            model_name="subscription",
            name="internal_notes",
            field=models.TextField(
                blank=True,
                help_text="Admin-only notes for this subscription (contracts, contacts, etc.).",
                null=True,
            ),
        ),
    ]
