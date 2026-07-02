from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from api.authenticate.models import Organization, OrganizationTenant, Token
from api.authenticate.subdomain_utils import extract_subdomain, validate_subdomain
from api.payments.models import Subscription, SubscriptionPlan
from django.core.exceptions import ValidationError


class SubdomainUtilsTests(TestCase):
    @override_settings(BASE_DOMAIN="masscer.ai")
    def test_extract_subdomain_prod_host(self):
        self.assertEqual(extract_subdomain("acme.masscer.ai"), "acme")
        self.assertIsNone(extract_subdomain("app.masscer.ai"))
        self.assertIsNone(extract_subdomain("masscer.ai"))
        self.assertIsNone(extract_subdomain("localhost"))

    def test_extract_subdomain_localhost(self):
        self.assertEqual(extract_subdomain("acme.localhost"), "acme")
        self.assertIsNone(extract_subdomain("app.localhost"))
        self.assertIsNone(extract_subdomain("localhost"))

    def test_validate_subdomain_reserved_and_format(self):
        self.assertEqual(validate_subdomain("acme-corp"), "acme-corp")
        with self.assertRaises(ValidationError):
            validate_subdomain("app")
        with self.assertRaises(ValidationError):
            validate_subdomain("-bad")


class OrganizationTenantAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(
            username="orgowner",
            email="owner@test.com",
            password="owner-password-123",
        )
        self.org = Organization.objects.create(name="Acme Org", owner=self.owner)
        self.login_token, _ = Token.get_or_create(user=self.owner, token_type="login")
        self.plan, _ = SubscriptionPlan.objects.get_or_create(
            slug="organization",
            defaults={
                "display_name": "Organization",
                "monthly_price_usd": Decimal("100"),
                "credits_limit_usd": Decimal("50"),
            },
        )

    def _auth_headers(self):
        return {"HTTP_AUTHORIZATION": f"Token {self.login_token.key}"}

    def _create_active_subscription(self):
        return Subscription.objects.create(
            organization=self.org,
            plan=self.plan,
            status="active",
            start_date=timezone.now(),
        )

    def test_get_tenant_defaults_when_missing(self):
        response = self.client.get(
            f"/v1/auth/organizations/{self.org.id}/tenant/",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNone(data.get("subdomain"))
        self.assertEqual(data.get("theme"), {})

    def test_claim_subdomain_requires_active_subscription(self):
        response = self.client.post(
            f"/v1/auth/organizations/{self.org.id}/tenant/subdomain/",
            data={"subdomain": "acme"},
            format="json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 403)

    def test_claim_and_release_subdomain(self):
        self._create_active_subscription()

        claim = self.client.post(
            f"/v1/auth/organizations/{self.org.id}/tenant/subdomain/",
            data={"subdomain": "acme"},
            format="json",
            **self._auth_headers(),
        )
        self.assertEqual(claim.status_code, 200)
        self.assertEqual(claim.json().get("subdomain"), "acme")

        tenant = OrganizationTenant.objects.get(organization=self.org)
        self.assertEqual(tenant.subdomain, "acme")

        release = self.client.delete(
            f"/v1/auth/organizations/{self.org.id}/tenant/subdomain/",
            **self._auth_headers(),
        )
        self.assertEqual(release.status_code, 200)
        self.assertIsNone(release.json().get("subdomain"))

    def test_update_tenant_branding(self):
        self._create_active_subscription()
        OrganizationTenant.objects.create(organization=self.org, subdomain="acme")

        response = self.client.put(
            f"/v1/auth/organizations/{self.org.id}/tenant/",
            data={
                "app_name": "Acme Portal",
                "hide_powered_by": True,
                "theme": {"primary_color": "#6e5bff"},
            },
            format="json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("app_name"), "Acme Portal")
        self.assertTrue(data.get("hide_powered_by"))
        self.assertEqual(data.get("theme", {}).get("primary_color"), "#6e5bff")

    def test_update_tenant_rejects_invalid_theme(self):
        self._create_active_subscription()
        OrganizationTenant.objects.create(organization=self.org)

        response = self.client.put(
            f"/v1/auth/organizations/{self.org.id}/tenant/",
            data={"theme": {"primary_color": "not-a-color"}},
            format="json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 400)

    @override_settings(BASE_DOMAIN="masscer.ai")
    def test_tenant_config_returns_branding(self):
        OrganizationTenant.objects.create(
            organization=self.org,
            subdomain="acme",
            app_name="Acme Portal",
            theme={"primary_color": "#112233"},
            hide_powered_by=True,
        )

        response = self.client.get(
            "/v1/auth/public/tenant-config",
            HTTP_HOST="acme.masscer.ai",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("app_name"), "Acme Portal")
        self.assertEqual(data.get("subdomain"), "acme")
        self.assertEqual(data.get("theme", {}).get("primary_color"), "#112233")
        self.assertTrue(data.get("hide_powered_by"))

    def test_tenant_config_empty_for_unknown_subdomain(self):
        response = self.client.get(
            "/v1/auth/public/tenant-config",
            HTTP_HOST="unknown.localhost",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {})
