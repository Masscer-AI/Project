from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from api.authenticate.models import Organization
from api.consumption.actions import register_consumption
from api.consumption.models import (
    Currency,
    OrganizationWallet,
    OrganizationWalletTransaction,
    Wallet,
)
from api.consumption.wallet_ops import organization_wallet_use_balance
from api.payments.billing_helpers import (
    forfeit_subscription_credits,
    recharge_org_wallet_compute_units,
)
from api.payments.models import Subscription, SubscriptionPlan


class WalletSplitTests(TestCase):
    def setUp(self):
        Currency.objects.get_or_create(name="Compute Unit", defaults={"one_usd_is": 1000})
        self.owner = User.objects.create_user("wallet_u1", "wallet_u1@ex.com", "pw-test-123")
        self.org = Organization.objects.create(name="Wallet Org", owner=self.owner)
        self.cu = Currency.objects.get(name="Compute Unit")

    def test_use_balance_drains_subscription_first(self):
        OrganizationWallet.objects.create(
            organization=self.org,
            subscription_balance=Decimal("100"),
            purchased_balance=Decimal("50"),
            unit=self.cu,
        )
        ok = organization_wallet_use_balance(self.org.id, Decimal("120"))
        self.assertTrue(ok)
        w = OrganizationWallet.objects.get(organization=self.org)
        self.assertEqual(w.subscription_balance, Decimal("0"))
        self.assertEqual(w.purchased_balance, Decimal("30"))

    def test_use_balance_insufficient_zeros_buckets(self):
        OrganizationWallet.objects.create(
            organization=self.org,
            subscription_balance=Decimal("10"),
            purchased_balance=Decimal("5"),
            unit=self.cu,
        )
        ok = organization_wallet_use_balance(self.org.id, Decimal("20"))
        self.assertFalse(ok)
        w = OrganizationWallet.objects.get(organization=self.org)
        self.assertEqual(w.subscription_balance, Decimal("0"))
        self.assertEqual(w.purchased_balance, Decimal("0"))

    def test_forfeit_subscription_credits_spares_purchased(self):
        OrganizationWallet.objects.create(
            organization=self.org,
            subscription_balance=Decimal("40"),
            purchased_balance=Decimal("10"),
            unit=self.cu,
        )
        forfeited = forfeit_subscription_credits(self.org)
        self.assertEqual(forfeited, Decimal("40"))
        w = OrganizationWallet.objects.get(organization=self.org)
        self.assertEqual(w.subscription_balance, Decimal("0"))
        self.assertEqual(w.purchased_balance, Decimal("10"))

    def test_forfeit_idempotent(self):
        OrganizationWallet.objects.create(
            organization=self.org,
            subscription_balance=Decimal("5"),
            purchased_balance=Decimal("0"),
            unit=self.cu,
        )
        forfeit_subscription_credits(self.org)
        forfeit_subscription_credits(self.org)
        w = OrganizationWallet.objects.get(organization=self.org)
        self.assertEqual(w.subscription_balance, Decimal("0"))

    def test_recharge_subscription_writes_ledger(self):
        OrganizationWallet.objects.create(
            organization=self.org,
            subscription_balance=Decimal("0"),
            purchased_balance=Decimal("0"),
            unit=self.cu,
        )
        recharge_org_wallet_compute_units(
            self.org,
            Decimal("5"),
            bucket=OrganizationWalletTransaction.BUCKET_SUBSCRIPTION,
            reason=OrganizationWalletTransaction.REASON_TRIAL_SEED,
        )
        w = OrganizationWallet.objects.get(organization=self.org)
        self.assertEqual(w.subscription_balance, Decimal("5"))
        self.assertEqual(
            OrganizationWalletTransaction.objects.filter(
                organization=self.org,
                reason=OrganizationWalletTransaction.REASON_TRIAL_SEED,
            ).count(),
            1,
        )


class RegisterConsumptionOrgEnforcementTests(TestCase):
    """Org-scoped consumption must never fall back to the personal Wallet."""

    def setUp(self):
        Currency.objects.get_or_create(name="Compute Unit", defaults={"one_usd_is": 1000})
        self.owner = User.objects.create_user("rc_u1", "rc_u1@ex.com", "pw-test-123")
        self.org = Organization.objects.create(name="RC Org", owner=self.owner)
        self.cu = Currency.objects.get(name="Compute Unit")
        self.plan, _ = SubscriptionPlan.objects.get_or_create(
            slug="organization",
            defaults={
                "display_name": "Org",
                "monthly_price_usd": Decimal("100"),
                "credits_limit_usd": Decimal("10"),
            },
        )

    def test_org_zero_balance_denies_without_personal_wallet(self):
        OrganizationWallet.objects.create(
            organization=self.org,
            subscription_balance=Decimal("0"),
            purchased_balance=Decimal("0"),
            unit=self.cu,
        )
        Subscription.objects.create(organization=self.org, plan=self.plan, status="active")
        ok = register_consumption(
            self.owner.id, Decimal("100"), organization_id=self.org.id
        )
        self.assertFalse(ok)
        self.assertFalse(
            Wallet.objects.filter(user_id=self.owner.id, unit=self.cu).exists()
        )

    def test_org_active_missing_wallet_denies_without_personal_wallet(self):
        Subscription.objects.create(organization=self.org, plan=self.plan, status="active")
        ok = register_consumption(
            self.owner.id, Decimal("100"), organization_id=self.org.id
        )
        self.assertFalse(ok)
        self.assertFalse(
            Wallet.objects.filter(user_id=self.owner.id, unit=self.cu).exists()
        )
