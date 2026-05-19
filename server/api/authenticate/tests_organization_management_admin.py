from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from api.authenticate.models import FeatureFlag, Organization
from api.consumption.models import Currency
from api.payments.models import Subscription, SubscriptionPayment, SubscriptionPlan


class OrganizationManagementAdminTests(TestCase):
    def setUp(self):
        Currency.objects.get_or_create(
            name="Compute Unit",
            defaults={"one_usd_is": 1000},
        )
        SubscriptionPlan.objects.get_or_create(
            slug="free_trial",
            defaults={
                "display_name": "Free Trial",
                "monthly_price_usd": Decimal("0"),
                "credits_limit_usd": Decimal("10"),
                "duration_days": 3,
            },
        )
        SubscriptionPlan.objects.get_or_create(
            slug="organization",
            defaults={
                "display_name": "Organization",
                "monthly_price_usd": Decimal("100"),
                "credits_limit_usd": Decimal("50"),
            },
        )
        SubscriptionPlan.objects.get_or_create(
            slug="custom",
            defaults={
                "display_name": "Custom (admin deals)",
                "monthly_price_usd": Decimal("0"),
                "credits_limit_usd": None,
                "duration_days": None,
                "is_configurable": True,
            },
        )
        self.owner = User.objects.create_user("owner1", "owner1@example.com", "pw-test-123")
        self.staff = User.objects.create_user(
            "staff1",
            "staff1@example.com",
            "pw-test-123",
            is_staff=True,
            is_superuser=True,
        )
        self.regular = User.objects.create_user("user1", "user1@example.com", "pw-test-123")
        self.org = Organization.objects.create(name="Acme Billing Co", owner=self.owner)
        self.client = Client()

    def test_changelist_staff_ok(self):
        self.client.force_login(self.staff)
        url = reverse("admin:authenticate_organizationmanagementproxy_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Acme Billing Co")

    def test_changelist_non_staff_forbidden(self):
        self.client.force_login(self.regular)
        url = reverse("admin:authenticate_organizationmanagementproxy_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_billing_detail_get_staff(self):
        self.client.force_login(self.staff)
        url = reverse(
            "admin:authenticate_organizationmanagementproxy_billing",
            args=[self.org.pk],
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Registered payments")
        self.assertContains(response, "Masscer subscriptions")

    def test_billing_detail_lists_all_masscer_subscription_rows(self):
        self.client.force_login(self.staff)
        org_plan = SubscriptionPlan.objects.get(slug="organization")
        active_sub = Subscription.objects.create(
            organization=self.org,
            plan=org_plan,
            status="active",
            payment_method="manual",
        )
        cancelled_sub = Subscription.objects.create(
            organization=self.org,
            plan=org_plan,
            status="cancelled",
            payment_method="manual",
        )
        url = reverse(
            "admin:authenticate_organizationmanagementproxy_billing",
            args=[self.org.pk],
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(active_sub.id))
        self.assertContains(response, str(cancelled_sub.id))
        self.assertContains(response, "Active + expired rows")
        self.assertContains(response, "Inactive rows")

    def test_billing_detail_groups_expired_rows_with_active_section(self):
        self.client.force_login(self.staff)
        org_plan = SubscriptionPlan.objects.get(slug="organization")
        active_sub = Subscription.objects.create(
            organization=self.org,
            plan=org_plan,
            status="active",
            payment_method="manual",
        )
        expired_sub = Subscription.objects.create(
            organization=self.org,
            plan=org_plan,
            status="expired",
            payment_method="manual",
        )
        url = reverse(
            "admin:authenticate_organizationmanagementproxy_billing",
            args=[self.org.pk],
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(active_sub.id))
        self.assertContains(response, str(expired_sub.id))
        self.assertContains(response, "View 2 active or expired Masscer subscription rows")

    def test_manual_subscription_updates_or_creates(self):
        self.client.force_login(self.staff)
        url = reverse(
            "admin:authenticate_organizationmanagementproxy_billing",
            args=[self.org.pk],
        )
        custom_plan = SubscriptionPlan.objects.get(slug="custom")
        response = self.client.post(
            url,
            {
                "action": "manual_subscription",
                "plan_id": str(custom_plan.pk),
                "status": "active",
                "billing_interval": "yearly",
                "contract_price_usd": "999.00",
                "credits_limit_usd": "100",
                "recharge_wallet": "on",
                "confirm_manual_subscription_revokes_previous": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        sub = Subscription.objects.filter(organization=self.org).order_by("-created_at").first()
        self.assertIsNotNone(sub)
        self.assertEqual(sub.payment_method, "manual")
        self.assertEqual(sub.plan.slug, "custom")
        self.assertEqual(sub.contract_price_usd, Decimal("999.00"))
        self.assertEqual(sub.credits_limit_usd, Decimal("100"))
        self.assertEqual(sub.billing_interval, "yearly")
        self.org.refresh_from_db()
        wallet = self.org.wallet
        self.assertGreater(wallet.subscription_balance, 0)

    def test_manual_subscription_over_stripe_requires_confirm(self):
        self.client.force_login(self.staff)
        url = reverse(
            "admin:authenticate_organizationmanagementproxy_billing",
            args=[self.org.pk],
        )
        org_plan = SubscriptionPlan.objects.get(slug="organization")
        custom_plan = SubscriptionPlan.objects.get(slug="custom")
        Subscription.objects.create(
            organization=self.org,
            plan=org_plan,
            status="active",
            payment_method="stripe",
            stripe_subscription_id="sub_test123",
            stripe_customer_id="cus_test123",
        )
        response = self.client.post(
            url,
            {
                "action": "manual_subscription",
                "plan_id": str(custom_plan.pk),
                "status": "active",
                "billing_interval": "monthly",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            Subscription.objects.filter(organization=self.org).count(),
            1,
        )

        response_ok = self.client.post(
            url,
            {
                "action": "manual_subscription",
                "plan_id": str(custom_plan.pk),
                "status": "active",
                "billing_interval": "monthly",
                "credits_limit_usd": "50",
                "contract_price_usd": "1200.00",
                "confirm_manual_subscription_revokes_previous": "on",
            },
        )
        self.assertEqual(response_ok.status_code, 302)
        self.assertEqual(
            Subscription.objects.filter(organization=self.org).count(),
            2,
        )
        latest = Subscription.objects.filter(organization=self.org).order_by("-created_at").first()
        self.assertEqual(latest.payment_method, "manual")
        self.assertEqual(latest.plan.slug, "custom")
        self.assertEqual(latest.credits_limit_usd, Decimal("50"))
        self.assertEqual(latest.contract_price_usd, Decimal("1200.00"))

        response_second = self.client.post(
            url,
            {
                "action": "manual_subscription",
                "plan_id": str(custom_plan.pk),
                "status": "active",
                "billing_interval": "monthly",
                "credits_limit_usd": "75",
                "contract_price_usd": "1500.00",
                "confirm_manual_subscription_revokes_previous": "on",
            },
        )
        self.assertEqual(response_second.status_code, 302)
        self.assertEqual(
            Subscription.objects.filter(organization=self.org).count(),
            3,
        )
        latest2 = Subscription.objects.filter(organization=self.org).order_by("-created_at").first()
        self.assertEqual(latest2.payment_method, "manual")
        self.assertEqual(latest2.plan.slug, "custom")
        self.assertEqual(latest2.credits_limit_usd, Decimal("75"))
        self.assertEqual(latest2.contract_price_usd, Decimal("1500.00"))

    def test_manual_subscription_requires_credit_budget_and_contract_price(self):
        self.client.force_login(self.staff)
        url = reverse(
            "admin:authenticate_organizationmanagementproxy_billing",
            args=[self.org.pk],
        )
        custom_plan = SubscriptionPlan.objects.get(slug="custom")
        before = Subscription.objects.filter(organization=self.org).count()
        self.client.post(
            url,
            {
                "action": "manual_subscription",
                "plan_id": str(custom_plan.pk),
                "status": "active",
                "billing_interval": "monthly",
                "credits_limit_usd": "",
                "contract_price_usd": "100.00",
                "confirm_manual_subscription_revokes_previous": "on",
            },
        )
        self.assertEqual(Subscription.objects.filter(organization=self.org).count(), before)
        self.client.post(
            url,
            {
                "action": "manual_subscription",
                "plan_id": str(custom_plan.pk),
                "status": "active",
                "billing_interval": "monthly",
                "credits_limit_usd": "50",
                "contract_price_usd": "",
                "confirm_manual_subscription_revokes_previous": "on",
            },
        )
        self.assertEqual(Subscription.objects.filter(organization=self.org).count(), before)
        self.client.force_login(self.staff)
        url = reverse(
            "admin:authenticate_organizationmanagementproxy_billing",
            args=[self.org.pk],
        )
        org_plan = SubscriptionPlan.objects.get(slug="organization")
        before = Subscription.objects.filter(organization=self.org).count()
        response = self.client.post(
            url,
            {
                "action": "manual_subscription",
                "plan_id": str(org_plan.pk),
                "status": "active",
                "billing_interval": "monthly",
                "confirm_manual_subscription_revokes_previous": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Subscription.objects.filter(organization=self.org).count(), before)

    def test_renew_active_subscription_extends_end_date_and_registers_payment(self):
        self.client.force_login(self.staff)
        url = reverse(
            "admin:authenticate_organizationmanagementproxy_billing",
            args=[self.org.pk],
        )
        custom_plan = SubscriptionPlan.objects.get(slug="custom")
        now = timezone.now()
        current_end = now + timedelta(days=18)
        sub = Subscription.objects.create(
            organization=self.org,
            plan=custom_plan,
            status="active",
            payment_method="manual",
            billing_interval="monthly",
            end_date=current_end,
            credits_limit_usd=Decimal("25"),
            contract_price_usd=Decimal("199.00"),
        )
        bal_before = self.org.wallet.total_balance
        response = self.client.post(
            url,
            {
                "action": "renew_subscription",
                "masscer_subscription_id": str(sub.id),
                "confirm_manual_renewal": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        sub.refresh_from_db()
        self.assertEqual(sub.status, "active")
        self.assertGreater(sub.end_date, current_end)
        self.org.wallet.refresh_from_db()
        self.assertGreater(self.org.wallet.total_balance, bal_before)
        pay = SubscriptionPayment.objects.filter(subscription=sub).latest("created_at")
        self.assertEqual(pay.amount_usd, Decimal("199.00"))
        self.assertIn("Manual renewal in admin", pay.notes)

    def test_renew_expired_subscription_restarts_from_now(self):
        self.client.force_login(self.staff)
        url = reverse(
            "admin:authenticate_organizationmanagementproxy_billing",
            args=[self.org.pk],
        )
        custom_plan = SubscriptionPlan.objects.get(slug="custom")
        now = timezone.now()
        sub = Subscription.objects.create(
            organization=self.org,
            plan=custom_plan,
            status="expired",
            payment_method="manual",
            billing_interval="monthly",
            end_date=now - timedelta(days=10),
            credits_limit_usd=Decimal("10"),
            contract_price_usd=Decimal("99.00"),
        )
        response = self.client.post(
            url,
            {
                "action": "renew_subscription",
                "masscer_subscription_id": str(sub.id),
                "confirm_manual_renewal": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        sub.refresh_from_db()
        self.assertEqual(sub.status, "active")
        self.assertGreater(sub.end_date, now)

    def test_renew_rejects_non_renewable_interval(self):
        self.client.force_login(self.staff)
        url = reverse(
            "admin:authenticate_organizationmanagementproxy_billing",
            args=[self.org.pk],
        )
        custom_plan = SubscriptionPlan.objects.get(slug="custom")
        sub = Subscription.objects.create(
            organization=self.org,
            plan=custom_plan,
            status="active",
            payment_method="manual",
            billing_interval="custom",
            credits_limit_usd=Decimal("10"),
            contract_price_usd=Decimal("99.00"),
        )
        before = SubscriptionPayment.objects.count()
        response = self.client.post(
            url,
            {
                "action": "renew_subscription",
                "masscer_subscription_id": str(sub.id),
                "confirm_manual_renewal": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SubscriptionPayment.objects.count(), before)

    def test_wallet_recharge(self):
        self.client.force_login(self.staff)
        url = reverse(
            "admin:authenticate_organizationmanagementproxy_billing",
            args=[self.org.pk],
        )
        org_plan = SubscriptionPlan.objects.get(slug="organization")
        Subscription.objects.create(
            organization=self.org,
            plan=org_plan,
            status="active",
            payment_method="manual",
        )
        self.assertTrue(hasattr(self.org, "wallet"))
        bal_before = self.org.wallet.purchased_balance
        response = self.client.post(
            url,
            {
                "action": "wallet_recharge",
                "amount_usd": "25",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.org.wallet.refresh_from_db()
        self.assertGreater(self.org.wallet.purchased_balance, bal_before)
        self.assertFalse(SubscriptionPayment.objects.exists())

    def test_wallet_recharge_blocked_without_active_masscer_subscription(self):
        self.client.force_login(self.staff)
        url = reverse(
            "admin:authenticate_organizationmanagementproxy_billing",
            args=[self.org.pk],
        )
        org_plan = SubscriptionPlan.objects.get(slug="organization")
        Subscription.objects.create(
            organization=self.org,
            plan=org_plan,
            status="cancelled",
            payment_method="manual",
        )
        bal_before = self.org.wallet.total_balance
        pur_before = self.org.wallet.purchased_balance
        response = self.client.post(
            url,
            {
                "action": "wallet_recharge",
                "amount_usd": "25",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.org.wallet.refresh_from_db()
        self.assertEqual(self.org.wallet.total_balance, bal_before)
        self.assertEqual(self.org.wallet.purchased_balance, pur_before)
        self.assertFalse(SubscriptionPayment.objects.exists())

    def test_wallet_recharge_can_register_payment(self):
        self.client.force_login(self.staff)
        url = reverse(
            "admin:authenticate_organizationmanagementproxy_billing",
            args=[self.org.pk],
        )
        org_plan = SubscriptionPlan.objects.get(slug="organization")
        sub = Subscription.objects.create(
            organization=self.org,
            plan=org_plan,
            status="active",
            payment_method="manual",
        )
        response = self.client.post(
            url,
            {
                "action": "wallet_recharge",
                "amount_usd": "25",
                "register_wallet_recharge_payment": "on",
                "wallet_recharge_payment_note": "Bank transfer received for wallet top-up.",
            },
        )
        self.assertEqual(response.status_code, 302)
        payment = SubscriptionPayment.objects.get()
        self.assertEqual(payment.subscription, sub)
        self.assertEqual(payment.amount_usd, Decimal("25"))
        self.assertEqual(payment.method, "manual")
        self.assertEqual(payment.status, "completed")
        self.assertEqual(payment.notes, "Bank transfer received for wallet top-up.")

    def test_wallet_recharge_register_payment_requires_note(self):
        self.client.force_login(self.staff)
        url = reverse(
            "admin:authenticate_organizationmanagementproxy_billing",
            args=[self.org.pk],
        )
        org_plan = SubscriptionPlan.objects.get(slug="organization")
        Subscription.objects.create(
            organization=self.org,
            plan=org_plan,
            status="active",
            payment_method="manual",
        )
        response = self.client.post(
            url,
            {
                "action": "wallet_recharge",
                "amount_usd": "25",
                "register_wallet_recharge_payment": "on",
                "wallet_recharge_payment_note": " ",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SubscriptionPayment.objects.exists())

    def test_toggle_feature_flag(self):
        self.client.force_login(self.staff)
        flag = FeatureFlag.objects.create(
            name="org-mgmt-test-flag-unique-xyz",
            organization_only=True,
        )
        url = reverse(
            "admin:authenticate_organizationmanagementproxy_billing",
            args=[self.org.pk],
        )
        response = self.client.post(
            url,
            {
                "action": "toggle_feature",
                "feature_flag_id": str(flag.pk),
                "enabled": "true",
            },
        )
        self.assertEqual(response.status_code, 302)
        from api.authenticate.models import FeatureFlagAssignment

        a = FeatureFlagAssignment.objects.get(organization=self.org, feature_flag=flag)
        self.assertTrue(a.enabled)

    @override_settings(STRIPE_SECRET_KEY="sk_test_fake")
    @patch("api.authenticate.organization_management_admin._stripe_cancel_at_period_end")
    def test_stripe_cancel_at_period_end_posts(self, mock_cancel):
        self.client.force_login(self.staff)
        org_plan = SubscriptionPlan.objects.get(slug="organization")
        sub = Subscription.objects.create(
            organization=self.org,
            plan=org_plan,
            status="active",
            payment_method="stripe",
            stripe_subscription_id="sub_test_cancel",
            stripe_customer_id="cus_test",
        )
        url = reverse(
            "admin:authenticate_organizationmanagementproxy_billing",
            args=[self.org.pk],
        )
        response = self.client.post(
            url,
            {
                "action": "stripe_cancel_at_period_end",
                "masscer_subscription_id": str(sub.id),
                "confirm_stripe_cancel": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        mock_cancel.assert_called_once_with("sub_test_cancel")

    @override_settings(STRIPE_SECRET_KEY="sk_test_fake")
    @patch("api.authenticate.organization_management_admin._stripe_cancel_at_period_end")
    def test_stripe_cancel_clears_stale_id_when_subscription_missing(self, mock_modify):
        import stripe

        mock_modify.side_effect = stripe.InvalidRequestError(
            "No such subscription: 'sub_gone'",
            param=None,
            code="resource_missing",
        )
        self.client.force_login(self.staff)
        org_plan = SubscriptionPlan.objects.get(slug="organization")
        sub = Subscription.objects.create(
            organization=self.org,
            plan=org_plan,
            status="active",
            payment_method="stripe",
            stripe_subscription_id="sub_gone",
            stripe_customer_id="cus_test",
        )
        url = reverse(
            "admin:authenticate_organizationmanagementproxy_billing",
            args=[self.org.pk],
        )
        response = self.client.post(
            url,
            {
                "action": "stripe_cancel_at_period_end",
                "masscer_subscription_id": str(sub.id),
                "confirm_stripe_cancel": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        sub.refresh_from_db()
        self.assertIsNone(sub.stripe_subscription_id)
