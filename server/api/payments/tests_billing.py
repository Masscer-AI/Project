from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from api.authenticate.models import Organization
from api.consumption.models import Currency, OrganizationWallet
from api.payments.billing_helpers import (
    expire_subscription_now,
    recharge_wallet_for_subscription_credits,
)
from api.payments.models import Subscription, SubscriptionPlan


class BillingHelpersSubscriptionTests(TestCase):
    def setUp(self):
        Currency.objects.get_or_create(name="Compute Unit", defaults={"one_usd_is": 1000})
        self.owner = User.objects.create_user("bill_u1", "bill_u1@ex.com", "pw-test-123")
        self.org = Organization.objects.create(name="Bill Org", owner=self.owner)
        self.cu = Currency.objects.get(name="Compute Unit")
        self.plan, _ = SubscriptionPlan.objects.get_or_create(
            slug="organization",
            defaults={
                "display_name": "Org",
                "monthly_price_usd": Decimal("100"),
                "credits_limit_usd": Decimal("10"),
            },
        )
        OrganizationWallet.objects.create(
            organization=self.org,
            subscription_balance=Decimal("5000"),
            purchased_balance=Decimal("3000"),
            unit=self.cu,
        )

    def test_expire_subscription_now_forfeits_subscription_bucket(self):
        sub = Subscription.objects.create(
            organization=self.org,
            plan=self.plan,
            status="active",
            end_date=timezone.now() + timedelta(days=5),
        )
        expire_subscription_now(sub)
        sub.refresh_from_db()
        self.assertEqual(sub.status, "expired")
        w = OrganizationWallet.objects.get(organization=self.org)
        self.assertEqual(w.subscription_balance, Decimal("0"))
        self.assertEqual(w.purchased_balance, Decimal("3000"))

    def test_recharge_wallet_for_subscription_credits_adds_subscription_bucket(self):
        sub = Subscription.objects.create(
            organization=self.org,
            plan=self.plan,
            status="active",
            credits_limit_usd=Decimal("2"),
        )
        w0 = OrganizationWallet.objects.get(organization=self.org)
        sub_before = w0.subscription_balance
        self.assertTrue(recharge_wallet_for_subscription_credits(sub))
        w = OrganizationWallet.objects.get(organization=self.org)
        self.assertEqual(w.subscription_balance, sub_before + Decimal("2000"))
