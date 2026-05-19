# Generated manually for subscription vs purchased wallet split.

import django.core.validators
from decimal import Decimal
from django.db import migrations, models
import django.db.models.deletion


def copy_balance_to_subscription(apps, schema_editor):
    OrganizationWallet = apps.get_model("consumption", "OrganizationWallet")
    for w in OrganizationWallet.objects.all().iterator():
        old = getattr(w, "balance", None)
        if old is not None:
            w.subscription_balance = old
            w.purchased_balance = Decimal("0")
            w.save(update_fields=["subscription_balance", "purchased_balance"])


class Migration(migrations.Migration):

    dependencies = [
        ("consumption", "0005_alter_consumption_amount_and_more"),
        ("payments", "0005_subscriptionplan_slug_custom_choice"),
    ]

    operations = [
        migrations.AddField(
            model_name="organizationwallet",
            name="purchased_balance",
            field=models.DecimalField(
                decimal_places=8,
                default=0,
                max_digits=20,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
            ),
        ),
        migrations.AddField(
            model_name="organizationwallet",
            name="subscription_balance",
            field=models.DecimalField(
                decimal_places=8,
                default=0,
                max_digits=20,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
            ),
        ),
        migrations.RunPython(copy_balance_to_subscription, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="organizationwallet",
            name="balance",
        ),
        migrations.CreateModel(
            name="OrganizationWalletTransaction",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "bucket",
                    models.CharField(
                        choices=[
                            ("subscription", "Subscription"),
                            ("purchased", "Purchased"),
                        ],
                        max_length=20,
                    ),
                ),
                ("delta", models.DecimalField(decimal_places=8, max_digits=20)),
                (
                    "reason",
                    models.CharField(
                        choices=[
                            ("trial_seed", "Trial seed"),
                            ("stripe_checkout", "Stripe checkout"),
                            ("stripe_renew", "Stripe renew"),
                            ("stripe_topup", "Stripe top-up"),
                            ("admin_recharge", "Admin wallet recharge"),
                            ("admin_manual_sub", "Admin manual subscription"),
                            ("forfeit_expiry", "Forfeit on subscription end"),
                            ("migration", "Data migration"),
                        ],
                        max_length=32,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="wallet_transactions",
                        to="authenticate.organization",
                    ),
                ),
                (
                    "subscription",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="wallet_transactions",
                        to="payments.subscription",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="organizationwallettransaction",
            index=models.Index(
                fields=["organization", "-created_at"],
                name="consumption_wtx_org_crt",
            ),
        ),
    ]
